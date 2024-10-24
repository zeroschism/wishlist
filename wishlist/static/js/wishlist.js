/* Wishlist functions */


function info(message, c="#msgbox") {
    var msgbox = $(c);
    msgbox.addClass("alert-success");
    msgbox.removeClass("d-none");
    msgbox.html(message);
}

function error(message, c="#msgbox") {
    var msgbox = $(c);
    msgbox.addClass("alert-danger");
    msgbox.removeClass("d-none");
    msgbox.html(message);
}

function clear_form() {
    $("form input").val("");
}    

function get_token() {
    const params = new Proxy(new URLSearchParams(window.location.search), {
        get: (searchParams, prop) => searchParams.get(prop),
    });

    return params.token;
}

function mark_got(item) {
    is_got = true;
    if ($(item).is(":checked")) {
        $(item).attr("disabled", true);
    } else {
        $(item).attr("disabled", false);
    }
}

function mark_item(item) {
    $.ajax({
        url: "/wishlist/"+wishlist_id+"/item/"+item.id+"/mark",
        data: JSON.stringify({ gotten: $(item).is(":checked"),token: get_token() }),
        type: "POST",
        dataType: "json",
        contentType: "application/json",
        success: function(json) {
            if (json.status == 1) {
                mark_got(item);
            } else {
                error(json.message);
                $(item).attr("checked",!$(item).is(":checked"));
            }
        }
    });
}

function delete_item(item) {
    $.ajax({
        url: "/wishlist/"+wishlist_id+"/item/"+item.id+"?token="+get_token(),
        type: "DELETE",
        dataType: "json",
        contentType: "application/json",
        success: function(json) {
            if (json.status == 1) {
                $(item).parent().parent().parent().remove();
                info(json.message);    
            } else {
                error(json.message);
            }
        },
        error: function(o,status,err) {
            error(o.responseJSON.message);
        }
    });         
}

function show_items(wishlist_id) {
    $.ajax({
        url: "/wishlist/"+wishlist_id+"/items?token="+get_token(),
        type: "GET",
        success: function(items_html) {
            $("#wishlist_items").html(items_html);
        }
    });
}

function add_item(e) {
    e.preventDefault();
    //JSON.stringify($("#addItem").serializeArray())
    var formData = {"name": $("#name").val(),"description":$("#description").val(),"url":$("#url").val()}
    $.ajax({
        url: "/wishlist/"+wishlist_id+"/item/add?token="+get_token(),
        data: JSON.stringify(formData),
        type: "POST",
        dataType: "json",
        contentType: "application/json",
        success: function(json) {
            if (json.status == 1) {
                info(json.message);
                show_items(json.id)
                clear_form();
            } else {
                error(json.message);
            }
        }
    });

    return false;
}

function create_wishlist(e) {
    e.preventDefault();
    var formData = {"name": $("#name").val(),"username":$("#username").val(),"email":$("#email").val()}
    $.ajax({
        url: "/wishlist/add",
        data: JSON.stringify(formData),
        type: "POST",
        dataType: "json",
        contentType: "application/json",
        success: function(json) {
            if (json.status == 1) {
                info(json.message);
                clear_form();
            } else {
                error(json.message);
            }
        }
    });

    return false;
}

function fallback_copy(url) {
    var textArea = document.createElement("textarea");
    textArea.value = url;

    textArea.style.top = "0";
    textArea.style.left = "0";
    textArea.style.position = "fixed";

    document.body.appendChild(textArea);
    textArea.focus();
    textArea.select();
    document.execCommand('copy');
    document.body.removeChild(textArea);
}

function copy_link(url) {
    if (!navigator.cipboard) {
        fallback_copy(url);
        return;
    }

    navigator.clipboard.writeText(url);
}

function share_email(e) {
    e.preventDefault();
    var formData = {"email": $("#share_email_input").val()}
    $.ajax({
        url: `/wishlist/${wishlist_id}/share?token=${get_token()}`,
        data: JSON.stringify(formData),
        type: "POST",
        dataType: "json",
        contentType: "application/json",
        success: function(json) {
            if (json.status == 1) {
                $("#share_email_modal").modal('hide');
                clear_form();
                info(json.message);
            } else {
                error(json.message, "#modal_msgbox");
            }
        },
        error: function(xhr, status, response) {
           error("An unexpected error occured. Try again later?", "#modal_msgbox");
        }
    });

    return false;
}
