const canvas=document.getElementById('marker'),ctx=canvas.getContext('2d');
    const title=document.getElementById('title'),product=document.getElementById('product');
    window.film={width:640,height:360,duration:2,ready:document.fonts.ready,frame(t,p){
      title.textContent=p.title;document.documentElement.style.setProperty('--brand',p.brand);
      product.style.transform=`translateY(${Math.sin(t*Math.PI)*-7}px) rotate(${Math.sin(t*Math.PI)*3}deg)`;
      ctx.clearRect(0,0,640,360);ctx.fillStyle='#00ffcc';ctx.fillRect(8+Math.round(t*12),8,14,8);
    }};