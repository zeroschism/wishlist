"""
    wishlist flask application for storing and sharing wishlists
    Copyright (C) 2024 Adam Schumacher

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU Affero General Public License as
    published by the Free Software Foundation, either version 3 of the
    License, or (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU Affero General Public License for more details.

    You should have received a copy of the GNU Affero General Public License
    along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""

import html
import wishlist.wishlist as wishlist
import wishlist.configuration as configuration
import wishlist.sendmail as sendmail
import json

from flask import Flask, render_template, make_response, request, session
from werkzeug.middleware.proxy_fix import ProxyFix


config = configuration.WishlistConfig("config.toml")
mailer = sendmail.Mailer(config.email.relay_server)


app = Flask("wishlist")

if config.app.is_proxied:
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

app.secret_key = config.app.session_key

@app.get("/")
def create_wishlist():
    if "id" not in session or not wishlist.verify_session(session["id"]):
        session["id"] = wishlist.new_session(request.remote_addr)
        app.logger.info(f"Created new session for {request.remote_addr}: {session['id']}")

    return render_template(
        "create_wishlist.html",
        title="Create Wishlist",
        description="Create a wishlist to share!",
        base_uri=config.app.base_uri,
    )

@app.post("/add")
def add_wishlist():
    if "id" not in session or not wishlist.verify_session(session["id"]):
        session["id"] = wishlist.new_session(request.remote_addr)
        app.logger.info(f"Created new session for {request.remote_addr}: {session['id']}")        

    wishlist_data = request.get_json()
    try:
        my_wishlist = wishlist.Wishlist(
            name=wishlist_data["name"],
            username=wishlist_data["username"],
            email=wishlist_data["email"],
        )
        wishdb = wishlist.WishlistDB()
        wishdb.add_wishlist(my_wishlist)
        wishdb.save()
        app.logger.info(f"[{session['id']}]: Created wishlist: {my_wishlist.id}")

        body = render_template(
            "email_verify.eml",
            name=my_wishlist.name,
            validate_url=f"{config.app.location}/{my_wishlist.id}?token={my_wishlist.owner_token}"
        )

        wishlist.check_mail_limit(my_wishlist.email)
        mailer.send_validate_email(my_wishlist, config.email.from_address, body)
        wishdb.sent_email(my_wishlist.email,session['id'])
        app.logger.info(f"Sent wishlist owner verification email to {my_wishlist.email}")
        resp = make_response(
            json.dumps(
                {
                    "status": 1,
                    "message": "We have sent the link to manage your wishlist to your email.  Check your email and save the link you received."
                }
            )
        )
    except wishlist.InvalidEmailError:
        app.logger.error("User entered a bad email address: {wishlist_data['email']}")
        resp = make_response(
            json.dumps({"status": 0, "message": html.escape("Please enter a valid email address")}),
            400
        )
    except wishlist.MissingRequiredParameterError as missing:
        app.logger.error(f"{missing}")
        resp = make_response(
            json.dumps({"status": 0, "message": html.escape(f"{missing}")}),
            400
        )
    except Exception as e:
        app.logger(f"Unable to add a new wishlist: {str(e)}")
        resp = make_response(
            json.dumps({"status": 0, "message": html.escape("Unable to add a wishlist due to some internal error.  Please try again")}),
            500
        )
    finally:
        resp.headers["Content-Type"] = "application/json"

    return resp

@app.get("/<uuid:wishlist_id>")
def view_wishlist(wishlist_id):
    if "id" not in session or not wishlist.verify_session(session["id"]):
        session["id"] = wishlist.new_session(request.remote_addr)
        app.logger.info(f"Created new session for {request.remote_addr}: {session['id']}")
    try:
        my_wishlist = wishlist.list_factory(wishlist_id)
        
        try:
            wishlist.verify_manage_token(my_wishlist, request.args.get("token", ""))
            self_view = True
            self_url = f"https://www.jupiterslament.net{config.app.base_uri}/{wishlist_id}?token={my_wishlist.owner_token}"
            share_url = f"https://www.jupiterslament.net{config.app.base_uri}/{wishlist_id}?token={my_wishlist.share_token}"
        except wishlist.InvalidManageToken:
            try:
                wishlist.verify_share_token(my_wishlist, request.args.get("token",""))                  
                self_view = False
                self_url = f"https://www.jupiterslament.net{config.app.base_uri}/{wishlist_id}?token={my_wishlist.share_token}"
                share_url = ""
            except wishlist.InvalidShareToken:
                return render_template("401.html", error_title="Invalid Token"), 401

        return render_template(
            "wishlist.html",
            title=f"{my_wishlist.name}",
            description="Things I'd like",
            wishlist_items=wishlist.get_items(my_wishlist),
            is_own=self_view,
            self_url=self_url,
            share_url=share_url,
            wishlist_id=str(wishlist_id),
            session_id=session["id"],
            base_uri=config.app.base_uri,
        )
    except wishlist.WishlistNotFoundError as nf:
        return (
            render_template(
                "404.html", error_title="Wishlist Not Found", message=str(nf)
            ),
            404,
        )
    except wishlist.UnverifiedWishlist as uw:
        return (
            render_template(
                "unverified.html", message=str(uw)
            ),
            403
        )

@app.post("/<uuid:wishlist_id>/share")
def share_wishlist(wishlist_id):
    if "id" not in session or not wishlist.verify_session(session["id"]):
        session["id"] = wishlist.new_session(request.remote_addr)
        app.logger.info(f"Created new session for {request.remote_addr}: {session['id']}")

    try:
        my_wishlist = wishlist.list_factory(wishlist_id)
        wishlist.verify_manage_token(my_wishlist,request.args.get("token",""))
        share_data = request.get_json()

        body = render_template(
            "email_share.eml",
            name=my_wishlist.username,
            share_url=f"{config.app.location}/{my_wishlist.id}?token={my_wishlist.share_token}",
        )
        
        # make sure we aren't sending too many emails
        wishlist.check_mail_limit(share_data["email"])
        # send_share_email will validate the address first
        mailer.send_share_email(my_wishlist, config.email.from_address, share_data["email"], body)
        wishdb = wishlist.WishlistDB()
        wishdb.sent_email(share_data["email"],session['id'])

        message = json.dumps(
                    {
                        "status": 1,
                        "message": f"Sent share link to {html.escape(str(share_data['email']).strip().lower())}",
                    }
                )
        code = 200
    except wishlist.WishlistNotFoundError as nf:
        message = json.dumps(
                    {
                        "status": 0,
                        "message": "Wishlist not found",
                    }
                )
        code = 404
    except wishlist.InvalidToken as invalid_token:
        message = json.dumps(
                    {
                        "status": 0,
                        "message": "Invalid token. Unable to share",
                    }
                )
        code = 401
    except wishlist.InvalidEmailError as email_error:
        message = json.dumps({
            "status": 0,
            "message": f"{html.escape(email_error)}"
        })
        code = 400
    except Exception as e:
        app.logger.error(f"[{session['id']}] Unable to share link: {e}")
        message = json.dumps({
            "status": 0,
            "message": "Unable to share link. Unknown error."
        })
        code = 500
    finally:
        return make_response(message, code)

@app.post("/<uuid:wishlist_id>/item/<uuid:item_id>/mark")
def mark_wishlist_item(wishlist_id, item_id):
    if "id" not in session or not wishlist.verify_session(session["id"]):
        session["id"] = wishlist.new_session(request.remote_addr)
        app.logger.info(f"Created new session for {request.remote_addr}: {session['id']}")
    try:
        update_data = request.get_json()
        my_wishlist = wishlist.list_factory(wishlist_id)
        wishlist.verify_share_token(my_wishlist, update_data["token"])
        wishlist.mark_item(
            wishlist_id, item_id, session["id"], update_data["gotten"]
        )
        resp = make_response(json.dumps({"status": 1, "message": "Updated"}))
    except Exception as e:
        resp = make_response(
            json.dumps({"status": 0, "message": html.escape(str(e))}), 500
        )
    finally:
        resp.headers["Content-Type"] = "application/json"

    return resp

@app.get("/<uuid:wishlist_id>/items")
def get_wishlist_items(wishlist_id):
    # wishlist.verify_any_token(wishlist_id,request.args.get('token',''))
    if "id" not in session or not wishlist.verify_session(session["id"]):
        session["id"] = wishlist.new_session(request.remote_addr)
        app.logger.info(f"Created new session for {request.remote_addr}: {session['id']}")

    try:
        my_wishlist = wishlist.list_factory(wishlist_id)

        if my_wishlist.owner_token == request.args.get("token", ""):
            self_view = True
        elif my_wishlist.share_token == request.args.get("token", ""):
            if not my_wishlist.email_verified:
                raise wishlist.UnverifiedWishlist("This wishlist has not yet been verified. If you created this wishlist, please check your email for the activation link.")
            self_view = False
        else:
            return render_template("invalid_token.html", title="You Wish", base_uri=config.app.base_uri), 401

        return render_template(
            "wishlist_items.html",
            wishlist_items=wishlist.get_items(my_wishlist),
            is_own=self_view,
            session_id=session["id"],
            base_uri=config.app.base_uri,
        )
    except wishlist.UnverifiedWishlist as uw:
        return (
            render_template(
            "unverified.html",
            content=str(uw)
            ),
            403
        )
    except Exception as e:
        app.logger.error(f"Unable to get wishlist items: {str(e)}")
        return (
            render_template("500.html", error_title="Failed to get items",message="We are sorry, but there was some unexpected error trying to retrieve your wishlist items"),
            500
        )

@app.post("/<uuid:wishlist_id>/item/add")
def add_wishlist_item(wishlist_id):
    if "id" not in session or not wishlist.verify_session(session["id"]):
        session["id"] = wishlist.new_session(request.remote_addr)
        app.logger.info(f"Created new session for {request.remote_addr}: {session['id']}")

    try:
        my_wishlist = wishlist.list_factory(wishlist_id)
        wishlist.verify_manage_token(my_wishlist,request.args.get("token",""))

        add_data = request.get_json()
        if not add_data:
            raise Exception("Unable to add: form is empty")
        else:
            print(f"data: {add_data}")

        item = wishlist.add_item(
            wishlist_id, add_data["name"], add_data["url"], add_data["description"]
        )
        resp = make_response(
            json.dumps(
                {
                    "status": 1,
                    "message": "Added item",
                    "id": str(wishlist_id),
                    "data": item,
                },
                cls=wishlist.WishlistJSONEncoder,
            )
        )
    except wishlist.InvalidToken:
        app.logger.error(f"Invalid or missing token for {wishlist_id}/item/add from {request.remote_addr}; token={request.args.get('token','')}")
        resp = make_response(
            json.dumps(
                {
                    "status": 0,
                    "message": "Invalid or missing manage token. Unable to add item.",
                }
            ),
            401
        )
    except wishlist.UnverifiedWishlist as uw:
        app.logger.warning(f"Attempt to add item to unverified wishlist; session={session}")
        resp = make_response(
            json.dumps(
                {
                    "status": 0,
                    "message": f"{html.escape(str(uw))}"
                }
            ),
            403
        )
    except Exception as e:
        
        print(f"error : {str(e)}")
        resp = make_response(
            json.dumps({"status": 0, "message": html.escape("Unable to add item due to internal error")}),
            500
        )
    finally:
        resp.headers["Content-Type"] = "application/json"

    return resp

@app.delete("/<uuid:wishlist_id>/item/<uuid:item_id>")
def delete_wishlist_item(wishlist_id, item_id):
    if "id" not in session or not wishlist.verify_session(session["id"]):
        session["id"] = wishlist.new_session(request.remote_addr)
        app.logger.info(f"Created new session for {request.remote_addr}: {session['id']}")

    try:
        my_wishlist = wishlist.list_factory(wishlist_id)
        wishlist.verify_manage_token(my_wishlist, request.args.get("token", ""))

        item = wishlist.item_factory(item_id, wishlist_id)
        if wishlist.remove_item(item_id, wishlist_id):
            resp = make_response(
                json.dumps(
                    {
                        "status": 1,
                        "message": f"Deleted item: {html.escape(item.name)}",
                    }
                )
            )
        else:
            resp = make_response(
                json.dumps({"status": 0, "message": "Nothing deleted"})
            )
    except wishlist.InvalidManageToken as inv:
        app.logger.error(f"Attempted to delete an item but had an invalid token")
        resp = make_response(
            json.dumps({"status": 0, "message": f"{html.escape('Invalid token!')}"}), 401
        )
    except wishlist.UnverifiedWishlist as uw:
        app.logger.warning(f"Attempt to delete item from unverified wishlist (?!?); session={session}")
        resp = make_response(
            json.dumps({"status": 0, "message": f"{html.escape(str(uw))}"}), 401
        )
    except Exception as e:
        resp = make_response(
            json.dumps({"status": 0, "message": html.escape(str(e))}), 500
        )
    finally:
        resp.headers["Content-Type"] = "application/json"

    return resp

@app.post("/recover")
def recover_wishlist():
    if "id" not in session or not wishlist.verify_session(session["id"]):
        session["id"] = wishlist.new_session(request.remote_addr)
        app.logger.info(f"Created new session for {request.remote_addr}: {session['id']}")

    try:
        email = request.get_json()
        if not email:
            raise wishlist.InvalidParameter("Please enter your email address!")
        else:
            #TODO: lookup email and send link if it exists
            return "Thanks!  We will do something with this, eventually", 200
    except Exception as e:
        app.logger.error(f"Unable to recover wishlist: {str(e)}; session={session}")
        pass