# Aplicación God’s Eye View

El visor desplegado inicia la aplicación original God’s Eye View: globo, controles nativos, catálogo **Data Layers**, escenas, integraciones de proveedores e interfaz de voz. `native/` añade capas de redes sociales y sensores al catálogo, un panel de evidencia, dos asistentes de texto y ajustes OCI, conservando la estructura de la aplicación nativa. La página standalone de `src/main.js` se conserva como fuente para revisión y pruebas; no es el punto de entrada de la imagen nativa ni un cliente anterior admitido.

## Fuente reproducible y atribución

Fuente upstream: [God’s Eye View de Bilawal Sidhu](https://github.com/bilawalsidhu/gods-eye-view), commit `aa16b7c3b0166a89d8c7a6089e0aff53a22faaee` (versión del paquete 0.2.1). El SHA-256 del archivo fuente es `a6020d0aa12a952585edee44a4765ab11f511e3f616927645d7ce04ce48487cb`.

[`upstream.json`](upstream.json) es la fuente autoritativa del commit fijado, las exclusiones y el manifiesto de parches. El archivo descargado y cada archivo fuente que se parchea deben coincidir con sus hashes; cada ancla de sustitución debe aparecer exactamente una vez. Una discrepancia detiene la preparación.

[`prepare_upstream.py`](prepare_upstream.py) genera el directorio ignorado `.upstream/` a partir del archivo fuente. Ese árbol generado no se incorpora al repositorio como código vendorizado ni se registra en Git. El preparador rechaza un directorio de salida que ya contenga archivos. Docker reproduce el árbol de forma independiente, sin depender del checkout generado de un desarrollador.

Los nueve parches de fuente verificados por hash son:

| Archivo upstream | Cambio de integración |
| --- | --- |
| `src/data/localGeojsonCore.js` | Expone helpers nativos de terreno y columnas reutilizados por las capas de sensores. |
| `src/main.js` | Delega en `native/main.js`. |
| `src/standalone/application.js` | Añade `extendCatalog(catalog, {scene, signal})` antes de cerrar los registros. |
| `src/app/constructCatalog.js` | Retira los registros del evento y localizador Bhote Koshi sujetos a restricciones. |
| `src/scenes/recipes.js` | Retira las recetas de eventos de Nepal y sus imports de datos restringidos. |
| `src/scenes/packs/defaults.js` | Retira el adaptador de presentación de la escena de Nepal. |
| `src/tools/index.js` | Retira la consulta de datos Bhote Koshi del registro de herramientas nativas. |
| `src/ui/rightPanelRail.js` | Admite el panel Agent Flow expandido y el límite compartido con el control de voz. |
| `src/ui/leftPanelRail.js` | Mantiene un espacio mínimo y respeta el límite inferior compartido de voz y HUD. |

La [licencia MIT del código upstream](https://github.com/bilawalsidhu/gods-eye-view/blob/aa16b7c3b0166a89d8c7a6089e0aff53a22faaee/LICENSE) y los avisos originales se conservan en el árbol generado y en la imagen. MIT cubre el código, pero no todos los datasets ni modelos incluidos. Esta distribución excluye el dataset de cables de TeleGeography bajo CC BY-NC-SA 3.0 y las imágenes y coordenadas derivadas de Bhote Koshi bajo CC BY-NC 4.0, incluido el dataset incrustado en JavaScript. También excluye la configuración de agentes, los workflows de GitHub y los medios de documentación upstream.

Las demás capas nativas y sus controles permanecen disponibles. Excluir el dataset de cables no proporciona datos de reemplazo; esa capa no dispone de datos sin una fuente con licencia adecuada. La cobertura, credenciales, cuotas y disponibilidad de los proveedores determinan qué capas en vivo funcionan en Bogotá. No presentar cámaras de otra ciudad como transmisiones de Bogotá.

La atribución de fuentes y proveedores conservados está documentada en [`DATA_SOURCES.md` upstream](https://github.com/bilawalsidhu/gods-eye-view/blob/aa16b7c3b0166a89d8c7a6089e0aff53a22faaee/DATA_SOURCES.md). Los datasets derivados de OpenStreetMap conservan sus obligaciones ODbL. Los modelos 3D conservados mantienen autores, enlaces de origen, licencias CC BY 4.0 y avisos de modificación en [`public/models/README.md` upstream](https://github.com/bilawalsidhu/gods-eye-view/blob/aa16b7c3b0166a89d8c7a6089e0aff53a22faaee/public/models/README.md). Los términos de cada proveedor se aplican independientemente de la licencia del código. Conservar estos avisos al redistribuir la imagen o los assets públicos.

El pequeño módulo de sesión MIT fijado en `vendor/gods-eye-view/` sigue siendo utilizado por el adaptador JSON AIDP probado. Su procedencia y lista de archivos permitidos son distintas del commit fijado para la fuente nativa completa; las pruebas del visor los verifican.

## Build y actualizaciones upstream

La imagen nativa usa Node 24.14.0. Su proceso de build es independiente del build de los controles de administración. Desde la raíz del repositorio:

```sh
python modules/ai-gods-eye-view/prepare_upstream.py --output modules/ai-gods-eye-view/.upstream
npm --prefix modules/ai-gods-eye-view/.upstream ci --ignore-scripts
node modules/ai-gods-eye-view/native/runtime.mjs --build
node --test modules/ai-gods-eye-view/tests/*.test.mjs
docker build -f modules/ai-gods-eye-view/Dockerfile -t gods-eye-view:dev .
```

La preparación exige un directorio de salida inexistente o vacío. `--archive` acepta un archivo descargado previamente y aplica la misma validación del checksum. `npm run build` en el directorio raíz del visor construye la página standalone conservada para revisión y pruebas; el build de la aplicación desplegada utiliza el comando nativo o Docker.

Para actualizar upstream, revisar el commit inmutable deseado y sus licencias, calcular los hashes del archivo fuente y de los archivos originales que se parchean, y revisar cada parche contra esa fuente antes de actualizar `upstream.json`. Materializar el resultado en un directorio vacío nuevo; no editar archivos generados para conseguir que pase un parche que falla. Ejecutar las pruebas del preparador y del visor, el build nativo, las comprobaciones de salud Docker y las verificaciones autenticadas de DOM/proveedores. Contrastar las nuevas rutas de proveedores con la lista fija permitida por el proxy. Una discrepancia de hash o ancla debe bloquear el proceso. La publicación posterior de una release inmutable exige su flujo verificado y autorización; publicar una release no acredita su despliegue ni aceptación OCI.

### Dependencias y límites de seguridad

El upstream fijado conserva avisos de dependencias. No ejecutar `npm audit fix` sobre el árbol generado: actualizar mediante una revisión o parche verificado, revisando consumidores, proxy y build. La [evidencia de aplicabilidad](../../docs/evidence/native-dependency-review.md) distingue rutas productivas de herramientas QA; no equivale a una auditoría limpia ni garantiza usos futuros.

## Límite de ejecución, entrega de imágenes y proveedores

El producto independiente ejecuta su propia API, visor y gateway TLS en una VM. El gateway es el único listener público, en 443; API 8000 y visor 8081 no publican puertos del host. Node permanece en loopback del contenedor, puerto 4173. No requiere el portal Starter Kits ni ofrece una segunda interfaz de instalación.

El proceso de build verifica el archivo upstream y sus parches y construye/prueba la aplicación nativa. El producto distribuye tres imágenes: API, visor y gateway. El empaquetador local `scripts/release/package_candidate.py` prepara un archivo `*-image-amd64.tar.gz` y un manifiesto `*-release.json` por componente, con commit, repositorio, plataforma `linux/amd64`, ID de contenido y SHA-256 real del archivo comprimido. No construye, descarga ni publica imágenes al empaquetar. CI entrega estos seis assets con `release=candidate`; no son instalables hasta preparar y verificar una release estable inmutable.

Deploy Studio obtiene la fuente y los seis assets de una release pública estable e inmutable, comprueba tag/commit y digests, y entrega metadata/rutas locales verificadas a los hooks. Estos revalidan manifiestos y bytes antes de staging CAS; no reciben tokens GitHub ni clonan una rama al arrancar. El esquema exacto y los límites de tamaño están en el [contrato de entrega](../../docs/private-artifact-handoff.md). La VM descarga los objetos mediante instance principal, verifica SHA antes de cargar e ID/plataforma después; Compose usa IDs locales con `pull_policy: never`.

El consumidor VM lee los tres objetos exactos mediante instance principal, verifica el SHA-256 antes de `docker load` y comprueba después el ID de contenido y la plataforma. Compose usa los IDs locales `sha256:...` en `API_IMAGE`, `VIEWER_IMAGE` y `GATEWAY_IMAGE`, con `pull_policy: never`. La VM no necesita tokens privados GitHub ni credenciales de registro. Su IAM se limita a los objetos de release y bootstrap autorizados. El arranque no clona una rama mutable ni recompila upstream. El control plane debe cumplir el contrato de entrega de los seis assets de una release estable inmutable; `candidate` no satisface ese gate. Las pruebas de componentes no sustituyen la aceptación de la integración instalada.

El visor supervisa el runtime original Node de proveedores/preview en `127.0.0.1:4173` y el bridge Python autenticado en 8081. El gateway sirve `/gods-eye-view/`, comprueba la sesión OIDC vigente con la API y solo reenvía los prefijos de API nativa permitidos. El bridge revalida de forma independiente la cookie en `/api/gods-eye-view/session` y sustituye los headers de identidad aportados por el navegador. `GODS_EYE_VIEW_ADMIN_URL` apunta a la API del producto (`http://api:8000` en Compose). La administración de proveedores vuelve a comprobar la sesión administradora en esa API; ninguna ruta pública expone `/internal/`. El bridge usa un destino local fijo, valida el origen público y no reenvía cookies de sesión ni credenciales OCI a los proveedores nativos. No es un proxy de URL arbitraria. No exponer directamente ninguno de los listeners de backend a Internet.

Los administradores autorizados abren **Source controls** dentro del visor nativo. Su diálogo del mismo origen incorpora `/controls/`, reutilizando componentes de horarios social/sensores, captura, evidencia, limpieza, parámetros de proveedores e identidad del visor. Gateway y API rechazan a los lectores en administración; ocultar el botón no es el control de permisos. Cerrar el diálogo no cancela una limpieza durable. Los controles editables extraídos y los hashes de su fuente congelada están en `apps/frontend/provenance.json`; su build usa `npm run build --prefix apps/frontend`. `docker/Gateway.Dockerfile` incorpora esos assets estáticos y `docker/compose.yml` define la red privada de servicios.

El bootstrap recibe configuración y credenciales OCI por el canal cifrado descrito en los contratos. La VM genera su clave TLS y su certificado de IP localmente; solo devuelve el certificado público y su huella por OCI autenticado. Exige las tres imágenes verificadas y ya cargadas por ID local inmutable. Si falla la activación y existe un recibo anterior, restaura sus imágenes y `runtime.env` y conserva el puntero vigente, sin reiniciar el estado de la API ni borrar la caché de proveedores. Ese rollback no revierte esquema Gold, IAM, claves OCI ni certificados TLS; una rotación o cambio incompatible requiere otra operación explícita. La publicación de workflows y la aceptación del agente siguen siendo independientes de la salud de los contenedores. Consultar [operación y recuperación](../../docs/operations.md).

El escritor nativo de claves y el transporte MCP no están habilitados en este despliegue. `/api/setup/status` presenta la disponibilidad de proveedores; las claves se administran en el entorno del servidor. Su ausencia permanece visible como falta de configuración. Los ajustes OCI utilizan endpoints de administración autenticados: región y credenciales son de solo lectura, y las opciones de modelo proceden del catálogo OCI disponible. Ningún formulario del navegador acepta una clave privada OCI, contraseña de base de datos ni cambio del endpoint.

Antes de iniciar el globo, `/api/setup/browser`, autenticado, devuelve exactamente `googleApiKey` y `cesiumToken` de la configuración del servidor en ejecución. Strings vacíos seleccionan explícitamente el funcionamiento sin claves. Una respuesta fallida o malformada detiene el arranque con un error, sin asumir que existen credenciales. Estas dos credenciales designadas por upstream para navegador son deliberadamente visibles al cliente y deben restringirse por dominio/API del proveedor y con ámbitos mínimos. Se cargan durante la ejecución; cambiarlas no exige reconstruir la imagen. No se permite proyectar el resto del entorno. Las credenciales OCI, de redes sociales y demás secretos del servidor permanecen exclusivamente en el servidor.

El globo puede iniciar con fuentes sin claves. Los tiles fotorrealistas de Google, servicios Cesium, voz nativa y otros feeds opcionales requieren sus claves y accesos respectivos. Conservar un control nativo no demuestra que su proveedor esté configurado ni que tenga cobertura geográfica.

## Rutas de asistentes y proveedores de voz

| Interfaz | Contrato y alcance |
| --- | --- |
| Agent Flow | `/api/gods-eye-view/chat`: una conversación AIDP con snapshot versionado, filtros/selección actuales, referencias de evidencia y botones explícitos de acciones del mapa. Respuesta JSON final; no utiliza OpenAI Realtime ni SSE. |
| Voz OpenAI | Integración OpenAI Realtime original upstream y herramientas nativas, con la clave OpenAI del servidor. |
| Voz OCI | Adaptador para el control de voz nativo. Un turno WAV acotado se envía a un modelo conversacional OCI con entrada de audio; `xai.grok-tts` genera la respuesta hablada. Es audio por turnos; no implementa OpenAI WebRTC ni streaming full-duplex. |

**Power up the globe** muestra el estado de los proveedores en modo de solo lectura. El despliegue aporta modelos y credenciales OCI; un navegador nuevo usa automáticamente la voz OCI configurada. Se conservan las preferencias explícitas existentes del navegador. Solo se instala un controlador de micrófono. La tarjeta OCI usa el indicador nativo del proveedor: verde significa que existen credenciales de servidor y un modelo configurado. El resultado de la última inferencia se mantiene separado; un error de cuota no borra la configuración. Se muestran los nombres legibles del catálogo en lugar de los OCID de modelos.

Con `GODS_EYE_VIEW_ENABLED=true`, los valores iniciales de un despliegue nuevo son `xai.grok-4.6` para texto y `google.gemini-2.5-flash-lite`, con voz `ara`, para los turnos de audio. El administrador puede cambiarlos mediante `GODS_EYE_OCI_TEXT_MODEL`, `GODS_EYE_OCI_VOICE_MODEL` y `GODS_EYE_OCI_VOICE` en el entorno de la VM. Las selecciones persistidas tienen prioridad. Estos valores reutilizan el operador, región y compartimento existentes; no ejecutan inferencia ni acreditan disponibilidad al arrancar.

Cuando el catálogo OCI devuelve `xai.grok-voice-agent`, la API administrativa lo presenta como **Realtime connection not verified**. El catálogo anuncia capacidades de audio y realtime, pero el adaptador todavía no implementa una sesión realtime OCI verificada para ese modelo. La opción permanece deshabilitada, sin dirigirla a Gemini o TTS bajo una etiqueta Grok Voice Agent. Disponibilidad en catálogo, configuración guardada e inferencia de voz correcta son comprobaciones distintas.

La voz OCI usa el operador y compartimento existentes del servidor. Ni el material PEM ni las credenciales de firma llegan al navegador. Los endpoints de audio aceptan grabaciones WAV PCM acotadas a 30 segundos; se mantienen los límites generales de cuerpos de petición de la API. Un turno de voz solo puede proponer acciones de cámara admitidas y cambios de visibilidad de capas, incluida **Social networks**. El cliente valida y ejecuta esas solicitudes; la respuesta de voz no confirma su ejecución. No puede ejecutar código, elegir una URL de backend ni confirmar un incidente. La evidencia publicada permanece en Agent Flow. Cancelar detiene las pistas del micrófono y la reproducción y descarta respuestas tardías. El audio se procesa para ese turno sin persistir grabaciones del micrófono en la aplicación.

El control nativo **ON/OFF** inicia turnos automáticos de audio: después de hablar, una pausa de 900 ms envía la grabación; la reproducción termina antes de volver a escuchar. Las ventanas de 30 segundos de solo silencio se reciclan localmente sin inferencia. El detector de amplitud exige 250 ms por encima de su umbral y puede confundir ruido sostenido con voz; validar los niveles del micrófono en la sala de demostración. No es voz realtime full-duplex. **OFF** o cualquier error del proveedor detiene la conversación. La aceptación del micrófono debe comprobar permiso, una frase hablada, la respuesta obtenida y la detención de las pistas de entrada. La UI no incluye controles para cargar archivos de prueba. Mantener esa aceptación separada de los tests unitarios o de una llamada correcta de texto a voz. Oracle documenta los contratos de [entrada de audio Gemini](https://docs.oracle.com/en-us/iaas/Content/generative-ai/google-gemini-2-5-flash.htm) y [salida de voz xAI](https://docs.oracle.com/en-us/iaas/Content/generative-ai/xai-grok-tts.htm).

Agent Flow es una sola conversación AIDP en el panel derecho nativo, debajo de **Context**. **Enter** envía una pregunta; **Shift+Enter** inserta una línea nueva. El botón **New conversation** de la cabecera reinicia el historial y contador. **Cancel** aborta una petición pendiente y descarta su respuesta tardía. Un `409` AIDP conserva la pregunta y actualiza la publicación para un reintento manual. Los botones de evidencia y acciones del mapa rechazan aplicar una respuesta de una publicación anterior. El resultado del modelo se representa como texto y nunca se ejecuta como HTML/código. El panel expandido respeta el límite de altura de **Data Layers**; la conversación se desplaza en su interior y el campo de escritura permanece visible.

`GODS_EYE_VIEW_MODE=oci` selecciona el runtime real. Configurarlo tanto en API como en visor, con el perfil del operador existente y los bindings AIDP del producto en el backend. Los controles utilizan Object Storage y las consultas analíticas utilizan AIDP Gold; Autonomous no es un prerrequisito de estas rutas. La independencia del repositorio no adopta ni migra automáticamente instalaciones anteriores; sus decisiones de transición requieren un operador autorizado y los contratos de operación.

`GODS_EYE_VIEW_ADMIN_URL` es obligatoria para obtener la publicación del backend autenticado en modo OCI. Si falta, el visor devuelve error; no selecciona una publicación fixture ni un lector alternativo. El modo OCI rechaza una publicación que no proceda del runtime AIDP. `/ready` del bridge comprueba el visor nativo y declara `publication_check=authenticated_backend_request`; la comprobación del backend y del snapshot es separada. La VM desplegada es la propietaria de captura; las comprobaciones locales no deben iniciar un segundo productor. Ni la ausencia de credenciales ni los fallos AIDP autorizan respuestas fixture. Los fixtures de desarrollo/pruebas permanecen identificados y no constituyen una pantalla de login local.

La capa God’s Eye View utiliza un solo `CustomDataSource` nativo. El sondeo de estado de captura sigue el horario del servidor y actualiza revisiones de publicación completadas. Desactivar la capa detiene su actualización y mantiene las demás capas. Una URL nueva inicializa un estado compartible de cámara de Bogotá antes del arranque; si ya existe un hash de navegación, lo conserva. No hay una corrección de cámara local diferida o periódica que compita con la navegación nativa o las vistas compartidas por usuarios.

Los periodos sociales inclusivos usan la fecha de creación de la publicación vinculada; los periodos de sensores son filtros explícitos sobre `observed_at`. Las últimas lecturas conocidas de sensores no heredan la ventana social predeterminada de 24 horas. Los filtros de área envían los mismos límites a AIDP. Los eventos sin coordenadas permanecen en la lista salvo que un área geográfica los excluya. Actividad, gravedad, confianza, corroboración y confirmación humana son conceptos distintos. La evidencia conserva su procedencia real o sintética. Solo se pueden mostrar fotos reales de X permitidas cuyos IDs de evidencia estuvieran incluidos en la revisión humana actual.

## Límites de aceptación

Las respuestas fixture locales están identificadas explícitamente y no invocan un modelo AIDP. Validar por separado los workflows nativos de la revisión instalada, la publicación Gold/Object, la conversación del agente y su concordancia con la evidencia. Una inferencia OCI directa correcta no acredita la ruta del agente AIDP, y una conversación de prueba no cambia el puntero activo. Los tests unitarios y la salud de contenedores no certifican voz en vivo, inferencia de modelos ni disponibilidad de feeds externos.

Los tests de componentes y los artifacts `candidate` no acreditan una instalación OCI ni una release estable. Verificar en el entorno instalado el listado de dominios, permisos, entrega de imágenes, confianza TLS, tareas/publicación, agente y voz que se utilicen. Mantener credenciales y diagnósticos sensibles fuera del repositorio público. Los [contratos del producto](../../docs/contracts.md), la [operación](../../docs/operations.md) y la [validación de desarrollo](../../docs/development.md) definen los límites y las comprobaciones correspondientes.
