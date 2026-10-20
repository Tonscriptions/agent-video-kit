const title=document.getElementById('title'),moving=document.getElementById('moving');
          window.film={ready:document.fonts.ready,frame(t){title.textContent=t<1?'EDIT VIDEO':'EDIT 2';
          moving.style.left=(180+Math.round(t*16))+'px';moving.hidden=Math.round(t*8)%2===0;}};