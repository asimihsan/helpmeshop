/* Author: Asim Ihsan

*/

function loggedIn(response)
{ 
    location.href = response.next_url; 
    /* alternatively you could do something like this instead: 
        $('#header .loggedin').show().text('Hi ' + response.first_name); 
     ...or something like that */ 
}

function gotVerifiedEmail(assertion)
{ 
    // got an assertion, now send it up to the server for verification 
    if (assertion !== null)
    { 
        $.ajax(
        { 
            type: 'POST', 
            url: '/login/browserid/', 
            data: { assertion: assertion }, 
            success: function(res, status, xhr)
            { 
                if (res === null) {}//loggedOut(); 
                else loggedIn(res); 
            }, 
            error: function(res, status, xhr)
            { 
                alert("login failure" + res); 
            } 
        }); 
    } 
    else
    { 
        //loggedOut(); 
    } 
}

$(function()
{ 
    $('#browserid').click(function()
    { 
        navigator.id.getVerifiedEmail(gotVerifiedEmail); 
        return false; 
    }); 
});



