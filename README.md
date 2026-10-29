# LG Remote+ — mando iPhone para LG webOS

**Estado:** versión de pruebas. El controlador antiguo ya funciona en un iPhone real según la prueba del usuario. La **nueva interfaz premium y el descubrimiento automático aún necesitan validación en su LG**.

## Descargar e instalar (sin ordenador ni túneles)

**ZIP completo:** https://github.com/DavidOrtegaLozano/tv-remote-universal/archive/refs/heads/main.zip

**Web de instalación:** https://tv-remote-universal.vercel.app

1. Descarga el ZIP en Safari en tu iPhone. Descomprímelo desde la aplicación Archivos.
2. En la carpeta descomprimida, localiza `iphone/`. **Conserva juntos los tres archivos:** `LG_REMOTE_PLUS.py`, `lg_remote_iphone.py` y `lg_discovery.py`.
3. En Pyto, abre **`LG_REMOTE_PLUS.py`** desde esa carpeta. Si Pyto te solicita acceso a la carpeta, concédeselo.
4. Ejecuta el archivo (▶). La app empieza a buscar televisores automáticamente. iPhone y LG deben estar en la misma Wi-Fi y LG debe estar encendido.
5. Toca el televisor detectado, acepta el permiso en su pantalla y empieza a usar el mando.
6. Si no aparece, pulsa **BUSCAR EN LA RED** otra vez y utiliza el campo de IP manual solo como último recurso.

### ¿Cómo funciona la detección?

- **Método prioritario SSDP/UPnP:** envía M-SEARCH a `239.255.255.250:1900` buscando `urn:lge-com:service:webos-second-screen:1`. Puede identificar TVs LG con nombre.
- **Televisor anterior:** prueba primero la IP recordada por el controlador; reutiliza la clave de emparejamiento local.
- **Respaldo TCP:** si SSDP no funciona, prueba puertos 3001 (y, en último término, 3000) de la subred local /24. En este modo muestra **«Posible LG»** porque un puerto abierto no demuestra la marca. Se valida al conectar y emparejar.
- **Manual:** disponible si la red bloquea la búsqueda, el móvil usa VPN, existe aislamiento entre clientes Wi-Fi o el televisor está en una subred distinta.

Los permisos de red local y los ajustes del router pueden afectar al descubrimiento. No se necesita servidor ni PC; todo ocurre dentro de Pyto en el iPhone.

## Interfaz premium
- Diseño oscuro con acentos verdes, selector de televisor y estado de conexión.
- Mando: cruceta grande con OK, Inicio, Atrás, Apagar, Volumen, Canal, Silencio y TV normal.
- Apps: listado dinámico de aplicaciones instaladas en webOS y apertura.
- HDMI: listado de entradas, selección, acceso a ajustes de imagen y campo de texto para búsquedas.

## Código

| Archivo | Función |
|---|---|
| `iphone/LG_REMOTE_PLUS.py` | **Ejecutar este**: interfaz visual para Pyto |
| `iphone/lg_discovery.py` | SSDP y descubrimiento de red |
| `iphone/lg_remote_iphone.py` | Controlador LG SSAP ya probado con el iPhone |
| `tests/test_premium.py` | Pruebas automáticas de detección y UI simulada |
| `tests/test_protocol.py` | Pruebas WebSocket con servidor simulado |
| `vercel/` | Web estática que explica la instalación en iPhone |

El controlador antiguo `lg_remote_iphone.py` sigue disponible como opción de recuperación. Si la nueva interfaz no abre, ejecútalo de nuevo sin modificarlo.

**Limitaciones:** no se ha verificado la UI premium con la versión exacta de Pyto del usuario. No incluye instalación automática de apps, regulador directo de brillo ni encendido desde apagado total. Es un proyecto no oficial, sin relación con LG Electronics.
