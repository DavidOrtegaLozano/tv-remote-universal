"""LG Remote+ Premium — iniciar este archivo en Pyto en el iPhone.
Colocar en la misma carpeta que lg_remote_iphone.py y lg_discovery.py.
"""
from concurrent.futures import ThreadPoolExecutor
import pyto_ui as ui
from mainthread import mainthread
from lg_remote_iphone import LGController
from lg_discovery import discover_tvs

INK=(8,18,31); PANEL=(19,37,55); TILE=(28,51,72)
MINT=(118,240,192); WHITE=(238,248,255); MUTED=(148,174,192)
RED=(245,112,123); GOLD=(255,202,121)
def c(rgb): return ui.Color.rgb(*(v/255 for v in rgb),1)

class PremiumRemote:
    def __init__(self):
        self.tv=LGController()
        self.connected=False
        self.name="Televisor LG"
        self.devices=[]
        self.page="tvs"
        self.offset=0
        self.busy=False
        self.alive=True
        self.worker=ThreadPoolExecutor(max_workers=1)
        self.root=ui.View();self.root.title="LG Remote+";self.root.size=(375,810)
        self.root.background_color=c(INK)
        self.head=ui.View();self.head.frame=(12,12,351,115)
        self.head.background_color=c(PANEL);self.head.corner_radius=22
        self.root.add_subview(self.head)
        self.label(self.head,"LG",17,15,41,43,24,MINT,True)
        self.label(self.head,"REMOTE+",63,17,245,30,22,WHITE,True)
        self.label(self.head,"Control directo por Wi-Fi",63,49,272,21,12,MUTED)
        self.notice=self.label(self.head,"●  Preparado para buscar",15,81,320,23,13,MINT)
        self.body=ui.View();self.body.frame=(10,139,355,582)
        self.body.background_color=c(INK);self.root.add_subview(self.body)
        self.nav=ui.View();self.nav.frame=(10,731,355,58)
        self.nav.background_color=c(PANEL);self.nav.corner_radius=18;self.root.add_subview(self.nav)
        self.draw()
        self.scan()

    def label(self,parent,text,x,y,w,h,sz=15,fg=WHITE,bold=False):
        el=ui.Label(text=str(text));el.frame=(x,y,w,h);el.text_color=c(fg)
        try:el.font=ui.Font("HelveticaNeue-Bold" if bold else "HelveticaNeue",sz)
        except Exception:pass
        parent.add_subview(el);return el

    def panel(self,x,y,w,h,bg=PANEL,r=17):
        el=ui.View();el.frame=(x,y,w,h);el.background_color=c(bg);el.corner_radius=r
        self.body.add_subview(el);return el

    def button(self,parent,title,x,y,w,h,action,bg=TILE,fg=WHITE,r=13,sz=16):
        el=ui.Button(title=title);el.frame=(x,y,w,h)
        el.background_color=c(bg);el.tint_color=c(fg);el.corner_radius=r
        try:el.font=ui.Font("HelveticaNeue-Bold",sz)
        except Exception:pass
        el.action=lambda sender:action()
        parent.add_subview(el);return el

    @mainthread
    def status(self,text,error=False):
        if self.alive:
            self.notice.text=str(text)[:64]
            self.notice.text_color=c(RED if error else MINT)

    def job(self,fn,done=None):
        if not self.alive:return
        def run():
            try:
                result=fn()
                if done:done(result)
            except Exception as exc:self.status("Error: "+str(exc),True)
        self.worker.submit(run)

    @mainthread
    def draw(self):
        if not self.alive:return
        for view in list(self.body.subviews):self.body.remove_subview(view)
        for view in list(self.nav.subviews):self.nav.remove_subview(view)
        pages=(("⌁ TV","tvs"),("◎ Mando","remote"),("▦ Apps","apps"),("▣ HDMI","inputs"))
        for i,(title,page) in enumerate(pages):
            active=self.page==page
            self.button(self.nav,title,5+i*87,6,84,46,
                        lambda p=page:self.goto(p),
                        MINT if active else PANEL,INK if active else MUTED,12,12)
        if self.page=="tvs":self.draw_tvs()
        elif self.page=="remote":self.draw_remote()
        elif self.page=="apps":self.draw_apps()
        else:self.draw_inputs()

    def goto(self,page):
        if page!="tvs" and not self.connected:
            self.status("Conecta primero con una TV",True)
            page="tvs"
        self.page=page;self.offset=0;self.draw()
        if page=="apps":self.load_apps()
        elif page=="inputs":self.load_inputs()

    def scan(self):
        if self.busy:return
        self.busy=True
        self.status("Buscando televisores LG en la red…")
        self.job(lambda:discover_tvs(saved_ip=self.tv.saved_ip(),progress=self.status),
                 self.found)

    @mainthread
    def found(self,devices):
        self.busy=False
        self.devices=devices or []
        self.status("Encontrados "+str(len(self.devices))+" dispositivos" if self.devices
                    else "No detectados; usa la IP manual")
        if self.page=="tvs":self.draw()

    def connect(self,ip,name="LG webOS"):
        if not ip:self.status("Introduce la IP del televisor",True);return
        self.status("Conectando con "+ip+"…")
        def do():
            self.tv.connect(ip,message=self.status)
            return ip,name
        self.job(do,self.ready)

    @mainthread
    def ready(self,data):
        self.connected=True;self.name=data[1];self.page="remote"
        self.status("●  Conectado a "+data[0]);self.draw()

    def command(self,fn,message="Comando enviado"):
        if not self.connected:self.status("Conecta la TV primero",True);return
        self.job(fn,lambda _:self.status("✓  "+message))

    def press(self,key):
        self.command(lambda:self.tv.press(key),key)

    def draw_tvs(self):
        self.label(self.body,"MIS TELEVISORES",10,4,324,35,21,WHITE,True)
        self.label(self.body,"Selecciona uno para controlar",10,38,330,24,13,MUTED)
        self.button(self.body,"↻    BUSCAR EN LA RED",10,77,335,51,
                    self.scan,MINT,INK,16,15)
        self.label(self.body,"DISPOSITIVOS DISPONIBLES",12,148,330,24,12,MUTED,True)
        if self.busy and not self.devices:
            self.label(self.body,"Explorando tu Wi-Fi…",16,191,310,30,15,GOLD)
        elif not self.devices:
            self.label(self.body,"No aparece ningún LG por ahora.",16,189,329,27,15,WHITE)
            self.label(self.body,"Enciende la TV y repite la búsqueda.",16,222,331,25,13,MUTED)
        for i,tv in enumerate(self.devices[:4]):
            p=self.panel(10,179+65*i,335,58)
            self.label(p,"▣",12,9,35,38,22,MINT)
            self.label(p,tv["name"][:26],51,5,230,25,14,WHITE,True)
            self.label(p,tv["ip"]+"  ·  "+tv["source"],51,29,250,23,12,MUTED)
            self.button(p,"›",289,6,37,44,
                        lambda tv=tv:self.connect(tv["ip"],tv["name"]),TILE,MINT,12,23)
        p=self.panel(10,454,335,113)
        self.label(p,"¿NO APARECE? IP MANUAL",12,10,306,24,12,MUTED,True)
        field=ui.TextField();field.frame=(12,41,217,53)
        field.placeholder="192.168.1.45";field.text=self.tv.saved_ip()
        field.background_color=c(TILE);field.text_color=c(WHITE);field.corner_radius=12
        p.add_subview(field)
        self.button(p,"Conectar",238,41,85,53,
                    lambda:self.connect(field.text.strip()),MINT,INK,11,12)

    def draw_remote(self):
        self.label(self.body,self.name[:27],10,4,270,35,21,WHITE,True)
        self.button(self.body,"⏻",290,2,55,48,
                    lambda:self.command(self.tv.power_off,"Apagando TV"),
                    (77,37,50),RED,17,24)
        p=self.panel(31,65,292,277,PANEL,35)
        pad=[("▲",103,15,86,73,"UP"),("◀",18,99,77,76,"LEFT"),
             ("OK",103,99,86,76,"ENTER"),("▶",197,99,77,76,"RIGHT"),
             ("▼",103,187,86,73,"DOWN")]
        for title,x,y,w,h,key in pad:
            center=key=="ENTER"
            self.button(p,title,x,y,w,h,lambda key=key:self.press(key),
                        MINT if center else TILE,INK if center else WHITE,37 if center else 25,23)
        self.button(self.body,"⌂  INICIO",11,352,157,44,
                    lambda:self.press("HOME"),TILE,WHITE,13,14)
        self.button(self.body,"↶  ATRÁS",186,352,158,44,
                    lambda:self.press("BACK"),TILE,WHITE,13,14)
        for i,(title,plus,minus) in enumerate((
            ("VOLUMEN",lambda:self.tv.volume(True),lambda:self.tv.volume(False)),
            ("CANAL",lambda:self.tv.channel(True),lambda:self.tv.channel(False)))):
            p=self.panel(11+175*i,409,158,100)
            self.label(p,title,14,8,125,24,12,MUTED,True)
            self.button(p,"+",11,39,63,49,lambda fn=plus:self.command(fn),TILE,WHITE,14,24)
            self.button(p,"−",84,39,63,49,lambda fn=minus:self.command(fn),TILE,WHITE,14,24)
        self.button(self.body,"◉  SILENCIO",11,518,157,49,
                    lambda:self.command(self.tv.mute),TILE,WHITE,13,12)
        self.button(self.body,"▣  TV NORMAL",186,518,158,49,
                    lambda:self.command(self.tv.live_tv),MINT,INK,13,12)

    def load_apps(self):
        self.status("Cargando aplicaciones…")
        self.job(self.tv.list_apps,lambda apps:self.list_ready("apps",apps))

    def load_inputs(self):
        self.status("Cargando entradas HDMI…")
        self.job(self.tv.list_inputs,lambda entries:self.list_ready("inputs",entries))

    @mainthread
    def list_ready(self,page,items):
        self.status(str(len(items or []))+" elementos disponibles")
        if self.page==page:self.draw()

    def rows(self,entries,act,limit=7):
        if not entries:
            self.label(self.body,"Sin elementos o cargando…",17,100,320,37,15,MUTED)
        for i,(title,entry_id) in enumerate(entries[self.offset:self.offset+limit]):
            p=self.panel(10,69+i*57,335,51)
            self.label(p,"▣",14,10,33,32,20,MINT)
            self.label(p,title[:27],49,8,231,34,14,WHITE,True)
            self.button(p,"›",291,7,35,37,
                        lambda entry_id=entry_id:act(entry_id),TILE,MINT,12,22)
        if self.offset:
            self.button(self.body,"‹ Anterior",11,478,150,40,
                        lambda:self.page_by(-limit),TILE,WHITE,12,12)
        if len(entries)>self.offset+limit:
            self.button(self.body,"Siguiente ›",193,478,150,40,
                        lambda:self.page_by(limit),TILE,WHITE,12,12)

    def page_by(self,diff):
        self.offset=max(0,self.offset+diff);self.draw()

    def draw_apps(self):
        self.label(self.body,"TUS APLICACIONES",10,3,290,42,20,WHITE,True)
        self.button(self.body,"↻",290,4,54,45,self.load_apps,TILE,MINT,12,21)
        self.rows(self.tv.apps or [],
                  lambda app:self.command(lambda:self.tv.launch_app(app),"App abierta"))

    def draw_inputs(self):
        self.label(self.body,"ENTRADAS Y ATAJOS",10,3,289,42,19,WHITE,True)
        self.button(self.body,"↻",290,4,54,45,self.load_inputs,TILE,MINT,12,21)
        self.rows(self.tv.inputs or [],
                  lambda item:self.command(lambda:self.tv.switch_input(item),"Entrada elegida"),4)
        self.button(self.body,"◉  AJUSTES DE IMAGEN",11,400,334,49,
                    lambda:self.command(self.tv.picture_settings),TILE,WHITE,13,13)
        self.label(self.body,"TEXTO PARA EL TELEVISOR",13,468,320,22,12,MUTED,True)
        field=ui.TextField();field.frame=(11,504,225,55)
        field.background_color=c(TILE);field.text_color=c(WHITE)
        field.placeholder="Escribe algo…";field.corner_radius=13
        self.body.add_subview(field)
        self.button(self.body,"Enviar",243,504,102,55,
                    lambda:self.command(lambda:self.tv.write_text(field.text),"Texto enviado"),
                    MINT,INK,13,13)

    def start(self):
        try:ui.show_view(self.root,ui.PRESENTATION_MODE_SHEET)
        finally:
            self.alive=False
            self.tv.close()
            self.worker.shutdown(wait=False)

if __name__=="__main__":
    PremiumRemote().start()
