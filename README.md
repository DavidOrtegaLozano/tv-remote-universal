# TV Remote Universal+ — GitHub + Vercel

**Estado:** proyecto experimental. La UI estática se puede desplegar, pero **el control de una TV física no está verificado**. LG webOS es el objetivo prioritario; Samsung y Roku son iniciales. No es un mando universal garantizado.

## 1. GitHub → Vercel (tu idea)

1. Crea un repositorio en GitHub, por ejemplo `tv-remote-universal`.
2. Copia **el contenido de esta carpeta** dentro del repositorio, respetando la estructura `vercel/`, `bridge/`, etc. No subas ningún archivo de `.remote-data/` (se crea en el PC).
3. En Vercel → **Add New → Project**, conecta GitHub, importa ese repositorio.
4. En la configuración del proyecto elige **Framework Preset: Other** y **Root Directory: `vercel`**. No hace falta `npm install` ni build del frontend.
5. Pulsa **Deploy**. Cada `git push` posterior a la rama de producción provocará un nuevo despliegue.

**Atención:** solamente se publica la **interfaz**. La TV está dentro de tu red doméstica y Vercel no puede conectarse directamente a ella. Si abres la web sin pasarela, verás el diseño pero no controlará nada.

## 2. Primero prueba la conexión local, ANTES de Vercel

1. Instala Node.js en Windows si hace falta. Descomprime/copia este proyecto en el ordenador.
2. Ejecuta `iniciar_en_windows.bat`. No cierres la consola.
3. Abre desde Safari (iPhone) la **URL completa que imprime**: `http://IP_DEL_PC:8787/?key=...`. El PC, iPhone y TV deben estar en la misma red local; evita Wi-Fi de invitados.
4. En el panel **Conectar** selecciona LG y prueba **Buscar**. Si no aparece, copia la IP de la TV desde sus Ajustes → Red y escríbela manualmente.
5. Pulsa **Diagnosticar conexión con la TV**. Verás si tu ordenador consigue abrir los puertos de control (3001/3000 LG, 8002/8001 Samsung, 8060 Roku).
6. Si hay algún puerto abierto, pulsa **Conectar y vincular**, acepta la solicitud que aparezca en el televisor y prueba Inicio, flechas, OK y volumen.

### Qué significa el diagnóstico

- **No carga la URL local en Safari**: revisa que el PC está encendido, que la consola sigue abierta, su IP, el firewall de Windows (permitir Node en redes **privadas**) y que iPhone no está conectado a datos móviles o red de invitados.
- **Carga, pero muestra acceso denegado**: vuelve a abrir el enlace completo con el parámetro `?key=...` o introduce la clave que imprime Windows.
- **No encuentra la TV automáticamente**: utiliza la IP manual; SSDP/multicast depende del router.
- **Puertos de TV cerrados/timeout**: confirma IP, que la TV esté encendida, Wi-Fi compartido y opción LG Connect Apps / acceso por dispositivo móvil en los ajustes del TV (nombre variable por webOS).
- **Puertos abiertos pero no solicita permiso o rechaza**: puede depender de la versión de webOS, firmware o permisos; guarda el mensaje exacto del panel y el modelo LG para ajustar el controlador.
- **Conecta pero los botones no responden**: indícanos qué botón y qué mensaje exacto aparece; algunos comandos dependen de permisos y versión.

*Nota:* un puerto abierto indica conectividad, no garantiza que el emparejamiento y los comandos funcionen.

## 3. Usar la web de Vercel para controlar la TV

Una vez que lo anterior funcione en local:

1. Ejecuta `iniciar_pasarela_vercel.bat` y escribe la URL final de Vercel: `https://tu-proyecto.vercel.app`.
2. Instala Cloudflare `cloudflared` y ejecuta `crear_tunel_https.bat` para generar una URL de prueba `https://...trycloudflare.com`.
3. Abre la web de Vercel en Safari, entra en **Conectar**, introduce la URL del túnel y la **clave completa de 36 caracteres** de la pasarela.
4. Pulsa Guardar y comprobar, elige la marca y escribe la IP del TV; usa **Diagnosticar conexión con la TV** y conecta.
5. Si te funciona: Safari → Compartir → Añadir a pantalla de inicio.

**Seguridad:** Cloudflare Quick Tunnel es exclusivamente para pruebas y expone un acceso temporal a la pasarela. No compartas la URL ni la clave, ni abras puertos en tu router. Para uso prolongado, configura un túnel estable con autenticación y controles de acceso. El ordenador sigue siendo necesario y debe estar encendido. Vercel NO hospeda la pasarela ni ejecuta Node para hablar con los dispositivos locales.

## 4. ¿Y sin ordenador ni túnel?

Una **app nativa iOS**, con permisos de red local, puede conectarse directamente a televisores compatibles. Es otra arquitectura y necesita compilación/firma para instalarse en el iPhone. Encontrar la TV no significa controlar cualquier modelo de cualquier marca: necesita controladores por protocolo.

## Desarrollo y tests

- Frontend de Vercel: `vercel/` (estático, HTML/CSS/JS)
- Frontend para probar desde PC: `app/`
- Pasarela local: `bridge/` (Node sin dependencias externas)
- Pruebas simuladas: `npm test` (no equivalen a una prueba real en hardware)
- Código experimental Flutter LG: `opcional_flutter_lg/`

Referencia de Vercel: https://vercel.com/docs/git/vercel-for-github