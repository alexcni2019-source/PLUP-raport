(() => {
 'use strict';
 const $=id=>document.getElementById(id),activation=document.querySelector('main').dataset.activation==='true';
 let token=new URLSearchParams(location.hash.slice(1)).get('token')||'';
 // Remove the secret fragment from the address/history once this page holds it.
 if(activation)history.replaceState(null,'',location.pathname);
 async function post(path,data){const response=await fetch(path,{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});const body=await response.json();if(!response.ok)throw Error(body.error||'Operațiunea nu a reușit.');return body;}
 async function init(){
  if(activation){try{const info=await post('/auth/invite-preview',{token});$('email').value=info.email;$('email').readOnly=true;$('intro').textContent='Alege o parolă proprie de 12–128 de caractere pentru contul invitat.';$('confirmation').hidden=false;$('repeat').required=true;$('member-form').hidden=false;$('password').focus();}catch(error){$('intro').textContent='Invitația nu poate fi folosită.';$('status').textContent=error.message;}}
  else{$('member-form').hidden=false;$('email').focus();}
 }
 $('member-form').addEventListener('submit',async event=>{event.preventDefault();if($('submit').disabled)return;if(activation&&$('password').value!==$('repeat').value){$('status').textContent='Parolele nu coincid.';$('repeat').focus();return;}$('submit').disabled=true;$('status').textContent='Se verifică…';try{await post(activation?'/auth/activate':'/auth/member-login',activation?{token,password:$('password').value}:{email:$('email').value,password:$('password').value});token='';$('password').value='';$('repeat').value='';location.replace('/');}catch(error){$('status').textContent=error.message;$('submit').disabled=false;}});
 void init();
})();
