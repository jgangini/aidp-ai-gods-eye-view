# Operación y recuperación

God’s Eye View se instala y actualiza desde Deploy Studio. La VM ejecuta gateway, API y visor mediante Compose; solo publica TLS 443. La administración de fuentes, horarios y proveedores está integrada en el visor. Instalar, reanudar o actualizar infraestructura no forma parte de esa interfaz.

El operador autorizado firma las peticiones OCI. El administrador elegido mediante Deploy Studio se comprueba como identidad activa del dominio y con permisos AIDP efectivos; seleccionarlo no cambia la identidad firmante. Los lectores no pueden administrar. La API revalida sesiones y permisos, incluida la revocación de acceso de una sesión abierta. Consultar los [contratos de identidad e instalación](contracts.md).

## Instalación nueva y recursos existentes

`aidp_mode=new` crea la plataforma y utiliza su workspace predeterminado; el post-apply verifica la asignación administrativa del seleccionado. `aidp_mode=existing` conserva la plataforma y el workspace indicados mediante sus claves exactas. Un catálogo externo se selecciona con `existing_catalog_key`; la coincidencia de un nombre no autoriza una adopción.

Los cinco buckets son distintos. Al compartirlos con otros productos, utilizar sus nombres, región y namespace reales y `create_buckets=false`. Conservar los recursos externos y sus permisos: cambiar este repositorio o ejecutar una actualización no transfiere Terraform state ni convierte esos recursos en propiedad de otra instalación. La VM tiene protección `prevent_destroy`; una sustitución o retirada exige una operación explícita y revisión de los datos e identidades que deben permanecer.

## Reintentos y Resume

El diario de instalación reside en artifacts bajo `.control/gods_eye_view/install/`. Usa escrituras condicionales CAS y un lease para excluir runners simultáneos. Vincula despliegue, plataforma, dominio, administrador y operador; las identidades de recursos verificadas se registran antes de reutilizarlas.

Ante un fallo, conservar el diario, los IDs de operación y los recursos. Reconciliar el resultado de la petición antes de iniciar otro intento. **Resume** vuelve a comprobar las identidades y permisos del mismo destino; no es una autorización para cambiar administrador, plataforma, workspace o catálogo, ni para adoptar recursos que se parezcan por nombre. Un lease vigente debe reconciliarse con su dueño; no borrarlo para forzar una segunda ejecución.

Si una creación de catálogo terminó sin devolver una identidad verificable, reconciliar esa petición antes de Resume. Un timeout de una operación OCI no demuestra que se canceló o que no creó recursos. No borrar recibos, checkpoints ni artefactos durables para ocultar un error. Los límites de recuperación asíncrona deben comprobarse en el entorno OCI que se opera.

## Receptor único y comprobación de imágenes

La plantilla de arranque instala `receive.py`, la unidad systemd oneshot `gods-eye-view-receiver.service` y un marcador de preparación. No inicia el receptor desde `user_data`: el runner es su único dueño y lo arranca después de publicar el sobre cifrado.

El servicio recibe las credenciales del operador, descarga los tres archivos de imagen mediante instance principal, comprueba sus hashes y sus IDs/plataforma, consume el objeto por ETag y ejecuta la activación Compose. El payload tiene exactamente `config`, `key`, `runtime_env` e `image_assets`; no acepta claves TLS externas. La VM no recibe credenciales GitHub ni de registro y usa imágenes locales `sha256:...` con `pull_policy: never`.

Resume puede iniciar la unidad aunque ya exista una clave temporal. Si el objeto ya fue consumido, el receptor solo reconoce una entrega completada cuando coincide el recibo de identidad y ya no existe la clave temporal. Después de terminar el servicio, el hook comprueba los tres IDs del recibo activo contra las imágenes solicitadas. Un rollback a imágenes anteriores no supera ese gate. La salud HTTPS y la verificación de tareas/publicación AIDP son comprobaciones adicionales; ninguna acredita por sí sola una conversación del agente.

La selección y la validación de los seis assets están definidas en el [contrato de entrega](private-artifact-handoff.md) y el [contrato de release](release-contract.md). El repositorio público permite obtener los assets de una release estable sin trasladar tokens al hook o a la VM; el runner conserva la responsabilidad de entregar metadata y archivos exactos y verificados.

## Update y revisión del host

El host declara protocolo `GODS_EYE_VIEW_HOST_V2` y una revisión SHA-256 que combina el hash del bundle con el hash de la plantilla `terraform/templatefile/user_data.sh`. El hook exige la revisión correspondiente a la fuente seleccionada antes de preparar un nuevo sobre o cargar las imágenes del producto.

Las actualizaciones de imágenes son admisibles cuando conservan esa revisión del host. Un helper ausente, otro protocolo o una revisión distinta detienen la entrega con diagnóstico de recuperación. Cambiar el bundle o la plantilla del host requiere una recuperación o migración autorizada y comprobada; no hay una actualización automática de esos scripts mediante `user_data`, que Terraform mantiene ignorado para la VM existente.

Mantener el commit, la release, los manifiestos y los seis assets vinculados. No sustituir archivos de una release inmutable ni descargar una rama móvil al arrancar. Una migración del host debe preservar AIDP, Gold, buckets, controles, identidades y permisos válidos; no crear recursos alternativos para sortear un conflicto. Las actualizaciones y la recuperación en una instalación viva necesitan su aceptación OCI.

## Activación y rollback

`docker/bootstrap.sh start` exige configuración preparada e IDs de las tres imágenes ya verificadas y cargadas. Adquiere un bloqueo local, comprueba el recibo anterior y guarda un recibo que vincula imágenes y `runtime.env`, con checksum y permisos privados. El puntero activo cambia tras la activación correcta.

Si la activación falla y existe un recibo anterior válido, restaura sus imágenes y `runtime.env` antes de comprobar su salud y conserva el puntero vigente. Si no existe una versión anterior recuperable, detenerse y reconciliar el fallo; no declarar éxito. La recuperación de contenedores no borra datos, controles, checkpoints, estado de API ni caché de proveedores.

Ese rollback no revierte esquema Gold, IAM, claves OCI ni certificados TLS. Las rotaciones y los cambios incompatibles necesitan una operación explícita, con snapshot y recuperación revisados. No activar una imagen antigua sobre un esquema o una identidad incompatibles. La proyección SQLite es reconstruible; Object Storage y Gold mantienen los datos durables.

## Confianza TLS y acceso OIDC

Terraform utiliza la IP pública asignada como origen HTTPS y registra `/api/auth/oci/callback` en ese mismo origen. La VM genera una clave RSA 3072 local y un certificado autofirmado anual con SAN de la IP. La clave privada permanece en la VM. OCI Run Command devuelve únicamente el PEM público canónico; Deploy Studio presenta `viewer_certificate_pem` y `viewer_certificate_sha256`.

Verificar la huella obtenida por ese canal autenticado antes de establecer confianza en el navegador o equipo. Si se guarda el PEM público en `viewer-certificate.pem`, puede consultarse su huella con:

```sh
openssl x509 -in viewer-certificate.pem -noout -fingerprint -sha256
```

Comparar con `viewer_certificate_sha256` ignorando los separadores `:` y las diferencias de mayúsculas. Establecer confianza explícita en esa hoja/IP según la política administrada del navegador/equipo antes de iniciar OIDC. No obtener la huella de confianza únicamente de una conexión de red sin verificar. El certificado no pertenece a una CA pública; el acceso inicial puede presentar un aviso de confianza.

El hook de salud usa exclusivamente la hoja obtenida por OCI y comprueba la IP; no desactiva TLS, no carga las CAs del sistema ni utiliza un proxy ambiental. Un certificado inválido, parcial, caducado o que no corresponda a la IP requiere recuperación explícita. No hay renovación automática ni gestión automática de un dominio/CA pública. Un cambio de IP requiere revisar tanto TLS como el callback OIDC. Nunca solicitar ni exportar la clave TLS privada para completar el acceso.

## Captura, publicación y aceptación

**Run** activa la captura y **Pause** evita capturas nuevas; pausar no detiene el compute ni borra checkpoints. Conservar los diarios de lotes para reintentar con los bytes originales y evitar duplicados o regeneración de evidencia. Los modos sintéticos, su agotamiento y su procedencia deben permanecer identificados.

Las consultas y las respuestas del agente se vinculan a una publicación Gold y a sus referencias de evidencia. Verificar tareas nativas de la revisión instalada, resultados publicados, permisos negativos, revocación y una conversación sustentada en esa misma publicación. `installed_conversation_pending` no equivale a aceptación de conversación. Una inferencia directa, un test fixture, un estado ACTIVE o la salud de los contenedores no acreditan todos esos resultados.

No se garantiza capacidad de lanzamiento, propagación IAM, disponibilidad/cuota de proveedores ni costes medidos por pasar checks locales o publicar una release. La [guía del visor](../modules/ai-gods-eye-view/README.md) detalla proveedores, voz, atribución y avisos de dependencias. La aplicabilidad de esos avisos debe revisarse cuando cambie el uso de las dependencias, conservando los pins y las verificaciones.
