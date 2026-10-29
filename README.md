# LG Remote+ — control LG desde iPhone sin ordenador

**Estado:** prototipo experimental; tests automatizados del protocolo correctos, prueba real con LG pendiente.

**Página de instalación:** https://tv-remote-universal.vercel.app

## Instalarlo sin PC ni Mac

### Opción A: interfaz con botones (Pyto)

1. Instalar Pyto IDE desde https://apps.apple.com/es/app/pyto-ide/id1436650069 (prueba gratuita limitada y posible compra después).
2. Desde Safari del iPhone, guardar el archivo https://raw.githubusercontent.com/DavidOrtegaLozano/tv-remote-universal/main/iphone/lg_remote_iphone.py en Archivos.
3. Abrir/importar el archivo en Pyto y pulsar Ejecutar.
4. Buscar la IP del televisor en Ajustes > Red; escribirla en el mando y pulsar Conectar.
5. Aceptar en la TV el mensaje de emparejamiento y probar Inicio, flechas, OK y volumen.

### Opción B: gratuita (a-Shell, terminal)

Instalar a-Shell desde https://apps.apple.com/es/app/a-shell/id1473805438 y ejecutar:

    curl -L https://raw.githubusercontent.com/DavidOrtegaLozano/tv-remote-universal/main/iphone/lg_remote_iphone.py -o lg_remote_iphone.py
    python3 lg_remote_iphone.py

Introducir IP de la TV y usar comandos: home, up, down, left, right, ok, back, vol+, vol-, ch+, ch-, mute, tv, apps, inputs, img, off, salir.

Ambas opciones ejecutan el controlador dentro del propio iPhone, en la misma red local que la TV. No requieren un PC encendido, túneles, claves de pasarela ni el servidor de Vercel. No son una IPA independiente.

## Funcionalidad (LG webOS solamente)

- Conexión SSAP WebSocket 3001 con alternativa 3000; emparejamiento y almacenamiento local de client-key.
- Navegación mediante socket pointer, volumen, mute, canales, abrir TV en directo y apagar.
- Lista y lanzamiento de apps instaladas, lista y cambio de entradas HDMI.
- Acceso a ajustes de imagen para modificar brillo manualmente.

No incluye instalación automática de apps, deslizador de brillo, encendido desde apagado, autodescubrimiento SSDP ni otras marcas. Compatibilidad dependiente del modelo/firmware. No está verificado con un LG físico.

## Arquitectura y seguridad

- iphone/lg_remote_iphone.py: Python 3.10+ sin dependencias externas. UI Pyto o terminal a-Shell.
- vercel/index.html: solo guía de instalación, desplegada desde main por GitHub/Vercel.
- tests/test_protocol.py y .github/workflows/tests.yml: tests automáticos con TV WebSocket simulada.

Solo se admiten IP privadas, el pointer socket debe apuntar a la misma TV, y la clave LG queda almacenada localmente en el iPhone. Se omite la validación TLS exclusivamente en la conexión a la IP local del televisor porque webOS suele usar un certificado autofirmado.

La antigua web necesitaba pasarela local Windows; deja de ser la solución recomendada. Si posteriormente se desea una app independiente vía TestFlight, es necesaria firma de Apple y normalmente cuenta Apple Developer de pago; puede compilarse en la nube sin Mac propio.

Proyecto no oficial, no afiliado a LG Electronics.