/* SPDX-License-Identifier: MIT
 * Copyright (c) 2026 Agent Video Kit contributors.
 * Original HSL kernel. Minimal ABI declarations follow the public frei0r 1 API:
 * https://github.com/dyne/frei0r/blob/master/include/frei0r.h
 * No upstream effect implementation or header is compiled into this module.
 */
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include <float.h>
#if defined(_WIN32)
#include <windows.h>
#endif

#if defined(_WIN32)
#define EXPORT __declspec(dllexport)
#else
#define EXPORT __attribute__((visibility("default")))
#endif

typedef struct { const char *name,*author; int plugin_type,color_model,frei0r_version,
    major_version,minor_version,num_params; const char *explanation; } PluginInfo;
typedef struct { const char *name; int type; const char *explanation; } ParamInfo;
typedef struct { uint32_t op,a,b,c; } Node;
typedef struct {
    size_t pixels; uint32_t count,roots[25]; Node *nodes;
    double *values; unsigned char *seen; char *text; int valid;
    const uint32_t *input; uint32_t *output; double parameters[25];
#if defined(_WIN32)
    PTP_WORK work; volatile LONG next_chunk;
#endif
} Instance;

#if defined(_WIN32)
static SRWLOCK pool_lock=SRWLOCK_INIT;
static PTP_POOL shared_pool=NULL;
static unsigned int pool_users=0;
static void CALLBACK process_chunks(PTP_CALLBACK_INSTANCE callback,void *context,PTP_WORK work);
#endif

/* Node arity: constant, time, +, -, *, /, unary -, clip, <, pow, exp, log, if. */
static const unsigned char arity[13]={0,0,2,2,2,2,1,3,2,2,1,1,3};
static const double centers[9]={0,30,60,120,180,240,270,300,360};
static double clamp(double v,double lo,double hi) { return v<lo?lo:v>hi?hi:v; }
static double absolute(double v) { return v<0?-v:v; }
static int finite_value(double v) { return v==v && v<=DBL_MAX && v>=-DBL_MAX; }
static uint32_t read32(const unsigned char *p) {
    return (uint32_t)p[0]|((uint32_t)p[1]<<8)|((uint32_t)p[2]<<16)|((uint32_t)p[3]<<24);
}
static int hex(char c) {
    return c>='0'&&c<='9'?c-'0':c>='a'&&c<='f'?c-'a'+10:-1;
}
static void clear_program(Instance *s) {
    free(s->nodes); free(s->values); free(s->seen); free(s->text);
    s->nodes=NULL; s->values=NULL; s->seen=NULL; s->text=NULL; s->count=0; s->valid=0;
}

static int load_program(Instance *s,const char *text) {
    size_t length=0,nbytes; unsigned char *raw=NULL,*depth=NULL; uint32_t n,i,j;
    clear_program(s);
    if (!text) return 0;
    while (length<=131072 && text[length]) ++length;
    if (length>131072 || length<224 || (length&1)) return 0;
    nbytes=length/2; raw=(unsigned char*)malloc(nbytes);
    if (!raw) return 0;
    for (i=0;i<nbytes;++i) {
        int a=hex(text[2*i]),b=hex(text[2*i+1]);
        if (a<0 || b<0) goto failed;
        raw[i]=(unsigned char)(a*16+b);
    }
    if (memcmp(raw,"AVKHSL01",8)) goto failed;
    n=read32(raw+8);
    if (!n || n>4096 || nbytes!=112+(size_t)n*16) goto failed;
    s->nodes=(Node*)calloc(n,sizeof(Node)); s->values=(double*)calloc(n,sizeof(double));
    s->seen=(unsigned char*)calloc(n,1); depth=(unsigned char*)calloc(n,1);
    if (!s->nodes || !s->values || !s->seen || !depth) goto failed;
    for (i=0;i<25;++i) { s->roots[i]=read32(raw+12+i*4); if(s->roots[i]>=n) goto failed; }
    for (i=0;i<n;++i) {
        Node *p=s->nodes+i; const unsigned char *r=raw+112+(size_t)i*16; unsigned int d=1;
        p->op=read32(r);p->a=read32(r+4);p->b=read32(r+8);p->c=read32(r+12);
        if(p->op>12) goto failed;
        if(p->op==0) { double v; memcpy(&v,&p->a,8); if(!finite_value(v)) goto failed; }
        else {
            const uint32_t children[3]={p->a,p->b,p->c};
            for(j=0;j<arity[p->op];++j) {
                if(children[j]>=i) goto failed;
                if((unsigned int)depth[children[j]]+1>d) d=(unsigned int)depth[children[j]]+1;
            }
        }
        if(d>128) goto failed; depth[i]=(unsigned char)d;
    }
    s->text=(char*)malloc(length+1); if(!s->text) goto failed;
    memcpy(s->text,text,length+1);s->count=n;s->valid=1;
    free(depth);free(raw);return 1;
failed:
    free(depth);free(raw);clear_program(s);return 0;
}

static double evaluate(Instance *s,uint32_t index,double time) {
    Node *p=s->nodes+index; double a,b,c,v;
    if(s->seen[index]) return s->values[index];
    if(p->op==0) memcpy(&v,&p->a,8);
    else if(p->op==1) v=time;
    else if(p->op==12) {
        a=evaluate(s,p->a,time);v=evaluate(s,a!=0?p->b:p->c,time);
    } else {
        a=evaluate(s,p->a,time);b=arity[p->op]>1?evaluate(s,p->b,time):0;
        c=arity[p->op]>2?evaluate(s,p->c,time):0;
        switch(p->op) {
        case 2:v=a+b;break;case 3:v=a-b;break;case 4:v=a*b;break;
        case 5:v=b!=0?a/b:NAN;break;case 6:v=-a;break;case 7:v=clamp(a,b,c);break;
        case 8:v=a<b?1:0;break;case 9:v=pow(a,b);break;case 10:v=exp(a);break;
        case 11:v=log(a);break;default:v=NAN;
        }
    }
    s->seen[index]=1;s->values[index]=v;return v;
}

EXPORT int f0r_init(void) {
#if defined(_WIN32)
    AcquireSRWLockExclusive(&pool_lock);
    if(!pool_users && !shared_pool) {
        shared_pool=CreateThreadpool(NULL);
        if(shared_pool) {
            SetThreadpoolThreadMaximum(shared_pool,3);
            if(!SetThreadpoolThreadMinimum(shared_pool,3)) {CloseThreadpool(shared_pool);shared_pool=NULL;}
        }
    }
    ++pool_users;ReleaseSRWLockExclusive(&pool_lock);
#endif
    return 1;
}
EXPORT void f0r_deinit(void) {
#if defined(_WIN32)
    AcquireSRWLockExclusive(&pool_lock);
    if(pool_users) --pool_users;
    if(!pool_users && shared_pool) {CloseThreadpool(shared_pool);shared_pool=NULL;}
    ReleaseSRWLockExclusive(&pool_lock);
#endif
}
EXPORT void f0r_get_plugin_info(PluginInfo *p) {
    p->name="Agent Video Kit selective HSL";p->author="Agent Video Kit contributors";
    p->plugin_type=0;p->color_model=1;p->frei0r_version=1;p->major_version=1;
    p->minor_version=0;p->num_params=1;p->explanation="Encoded RGB eight-band HSL, exact alpha and bounded author-clock DAG";
}
EXPORT void f0r_get_param_info(ParamInfo *p,int index) {
    (void)index;p->name="program";p->type=4;p->explanation="Validated AVKHSL01 program, lowercase hex";
}
EXPORT void *f0r_construct(unsigned int w,unsigned int h) {
    Instance *s;
    if(!w || !h || w>8192 || h>8192) return NULL;
    s=(Instance*)calloc(1,sizeof(Instance));if(!s) return NULL;s->pixels=(size_t)w*h;
#if defined(_WIN32)
    if(shared_pool && s->pixels>=16384) {
        TP_CALLBACK_ENVIRON environment;
        InitializeThreadpoolEnvironment(&environment);SetThreadpoolCallbackPool(&environment,shared_pool);
        s->work=CreateThreadpoolWork(process_chunks,s,&environment);
        DestroyThreadpoolEnvironment(&environment);
    }
#endif
    return s;
}
EXPORT void f0r_destruct(void *instance) {
    Instance *s=(Instance*)instance;if(!s) return;
#if defined(_WIN32)
    if(s->work) {WaitForThreadpoolWorkCallbacks(s->work,FALSE);CloseThreadpoolWork(s->work);}
#endif
    clear_program(s);free(s);
}
EXPORT void f0r_set_param_value(void *instance,void *value,int index) {
    if(instance && value && index==0) load_program((Instance*)instance,*(char**)value);
}
EXPORT void f0r_get_param_value(void *instance,void *value,int index) {
    if(instance && value && index==0) *(char**)value=((Instance*)instance)->text;
}
static void process_pixels(Instance *s,size_t first,size_t end) {
    const uint32_t *input=s->input;uint32_t *output=s->output;const double *parameters=s->parameters;
    size_t i;unsigned int k;
    for(i=first;i<end;++i) {
        const unsigned char *src=(const unsigned char*)(input+i);unsigned char *dst=(unsigned char*)(output+i);
        double r=src[0]*(1./255),g=src[1]*(1./255),b=src[2]*(1./255);
        double high=r>g?(r>b?r:b):(g>b?g:b),low=r<g?(r<b?r:b):(g<b?g:b),difference=high-low;
        double h,l=(high+low)/2,saturation,weight,dh,ds,dl,chroma,x,m,c[3];int sector,left,right;
        if(difference==0) { output[i]=input[i];continue; }
        saturation=difference/(1-absolute(2*l-1));
        if(high==r) {h=(g-b)/difference;if(h<0) h+=6;h*=60;}
        else if(high==g) h=60*((b-r)/difference+2);
        else h=60*((r-g)/difference+4);
        right=1;while(right<8 && h>=centers[right]) ++right;
        left=right-1;weight=(h-centers[left])/(centers[right]-centers[left]);right%=8;
        dh=(1-weight)*parameters[left*3]+weight*parameters[right*3];
        ds=(1-weight)*parameters[left*3+1]+weight*parameters[right*3+1];
        dl=(1-weight)*parameters[left*3+2]+weight*parameters[right*3+2];
        saturation=clamp(ds>=0?saturation+(1-saturation)*ds:saturation*(1+ds),0,1);
        l=clamp(dl>=0?l+(1-l)*dl:l*(1+dl),0,1);
        h+=dh+360;h=(h-360*(int)(h/360))*(1./60);
        chroma=(1-absolute(2*l-1))*saturation;sector=(int)h;
        x=chroma*((sector&1)?1-(h-sector):h-sector);m=l-chroma/2;
        switch(sector) {
        case 0:c[0]=chroma;c[1]=x;c[2]=0;break;case 1:c[0]=x;c[1]=chroma;c[2]=0;break;
        case 2:c[0]=0;c[1]=chroma;c[2]=x;break;case 3:c[0]=0;c[1]=x;c[2]=chroma;break;
        case 4:c[0]=x;c[1]=0;c[2]=chroma;break;default:c[0]=chroma;c[1]=0;c[2]=x;
        }
        for(k=0;k<3;++k) dst[k]=(unsigned char)(clamp(src[k]+((c[k]+m)*255-src[k])*parameters[24],0,255)+.5);
        dst[3]=src[3];
    }
}

#if defined(_WIN32)
static void CALLBACK process_chunks(PTP_CALLBACK_INSTANCE callback,void *context,PTP_WORK work) {
    Instance *s=(Instance*)context;LONG chunk;(void)callback;(void)work;
    while((size_t)(chunk=InterlockedIncrement(&s->next_chunk)-1)*32768<s->pixels) {
        size_t first=(size_t)chunk*32768,end=first+32768;
        process_pixels(s,first,end<s->pixels?end:s->pixels);
    }
}
#endif

EXPORT void f0r_update(void *instance,double time,const uint32_t *input,uint32_t *output) {
    Instance *s=(Instance*)instance;unsigned int k;
    if(!s || !input || !output) return;
    if(!s->valid) {memmove(output,input,s->pixels*4);return;}
    memset(s->seen,0,s->count);
    for(k=0;k<25;++k) {
        double v=evaluate(s,s->roots[k],time);
        if(!finite_value(v)) {memmove(output,input,s->pixels*4);return;}
        s->parameters[k]=clamp(v,k==24?0:k%3==0?-180:-1,k==24?1:k%3==0?180:1);
    }
    if(s->parameters[24]==0) {memmove(output,input,s->pixels*4);return;}
    s->input=input;s->output=output;
#if defined(_WIN32)
    if(s->work) {
        s->next_chunk=0;for(k=0;k<3;++k) SubmitThreadpoolWork(s->work);
        process_chunks(NULL,s,NULL);WaitForThreadpoolWorkCallbacks(s->work,FALSE);return;
    }
#endif
    process_pixels(s,0,s->pixels);
}

/* Useful to local build tests; never executes a frame or loads external code. */
EXPORT int avk_hsl_validate_program(const char *text) {
    Instance s={0};int valid=load_program(&s,text);clear_program(&s);return valid;
}
