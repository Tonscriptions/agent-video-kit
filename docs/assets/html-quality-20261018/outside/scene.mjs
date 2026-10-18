const title=document.getElementById('title'),product=document.getElementById('product');
      window.film={width:384,height:216,duration:2,ready:document.fonts.ready,frame(t){
        title.textContent=t<1?"EDIT VIDEO":"EDIT 2";
        product.style.transform=`translateY(${Math.round(Math.sin(t*Math.PI)*-8)}px)`;
      }};
const draw=window.film.frame;window.film.frame=(t,p)=>{draw(t,p);title.style.left=(t<1.5?24:384)+"px"};
