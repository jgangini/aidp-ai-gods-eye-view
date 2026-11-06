# Contratos del candidato

El ID del producto es `gods_eye_view`; el proyecto Deploy Studio es `aidp-ai-gods-eye-view`. Las identidades persistentes del dataset y Workspace se conservan. El inventario inicial describe la fuente; los archivos actuales y sus pruebas describen este candidato.

## Interfaz e identidad

La única interfaz está en `/gods-eye-view/`; abre los controles integrados `/controls/` para administradores. `/api/gods-eye-view/session` revalida cuenta y membresía; `/api/admin/session` exige además el `admin_user_ocid` seleccionado y permisos AIDP efectivos, incluidos grupos y roles heredados. La API rechaza headers de identidad externos como autorización y comprueba las mutaciones en servidor. OIDC utiliza callback `/api/auth/oci/callback`, PKCE, firma, issuer, audience, nonce y vigencia.

El gateway elimina headers aportados por el cliente. Node y el bridge carecen de puertos públicos. La API no expone instalación HTTP ni registro/login local. Las transacciones OIDC y límites son por proceso: una sola instancia/worker hasta implementar almacenamiento compartido.

## Instalación desde Deploy Studio

`terraform/deploy-studio.json` usa schema 1 y el selector común `oci_aidp_administrators`. Se validó con el modelo Pydantic y extractor de archivo reales de CloudTechNext, incluidos entrypoints e include_paths. Esa validación local no demuestra instalación cloud.

El usuario elige `identity_domain_id`, `admin_user_ocid`, `aidp_mode=new|existing` y, para existente, `existing_ai_data_platform_ocid` y `existing_workspace_key`. Los hooks vuelven a comprobar identidad/dominio/roles en instalación y Resume. La plataforma nueva concede explícitamente `AI_DATA_PLATFORM_ADMIN` al seleccionado y verifica el resultado. El operador conserva su propia identidad firmante; la selección no lo suplanta ni crea otro provisioner.

Las cuatro selecciones medallion y artifacts son distintas. Un catálogo externo requiere `existing_catalog_key` exacto; encontrar un nombre coincidente no autoriza adoptarlo. Los recursos externos no entran al state como recursos a destruir. Los recibos operativos usan CAS, identidad exacta y exclusión de runners.

Preflight selecciona automáticamente una imagen pública Oracle Linux 9 compatible con VM.Standard.E5.Flex y un availability domain compatible, con paginación OCI; conserva los IDs ya fijados en Resume. La capacidad efectiva de lanzamiento sigue pendiente de OCI. Terraform deriva `public_origin` de la IP pública asignada a la VM y registra ese mismo origen en el callback OIDC; no requiere dominio ni certificado del usuario. La VM necesita salida a repositorios de paquetes y a OCI. La identidad de instancia solo lee el bundle fijado y consume el objeto cifrado de su despliegue. La política de servicio AIDP nueva se declara separadamente de las referencias externas. La propagación real de IAM queda por aceptar en OCI.

## Artefactos privados y secretos

El bootstrap de VM es un ZIP determinista de cuatro archivos públicos de aplicación: Compose, script de arranque, receptor cifrado y cargador de imágenes verificadas. Preflight deriva su SHA-256 y objeto `releases/<commit>/vm-bootstrap-<hash>.zip` de los bytes del código fijado y los devuelve como runtime inputs; no se piden al usuario. Post-apply verifica los bytes y los publica condicionalmente en el bucket artifacts. La VM los lee mediante instance principal y verifica el hash: no necesita PAT para descargar fuente GitHub ni clona repositorios privados al arrancar.

El manifiesto declara seis `release_assets`: preflight descarga tres manifiestos JSON y recibe metadata de los tres archivos de imagen; post-apply recibe los seis archivos verificados. El control plane es dueño de la autorización GitHub. Entrega `context.release_assets` con repositorio, ref, commit, release ID y metadata/rutas locales; no pasa token, URL ni headers a los hooks. El consumidor del producto revalida los bindings, manifiestos y bytes locales antes de publicar objetos OCI mediante CAS.

El [contrato exacto de handoff](private-artifact-handoff.md) distingue la adaptación del consumidor y la integración CTN pendiente de aceptación. Los hooks rechazan un handoff ausente o inválido antes de mutar recursos; no suponen `GH_TOKEN`/`GITHUB_TOKEN` ni credenciales GitHub en inputs secretos. El descargador HTTP aislado se conserva con sus pruebas, pero no es la ruta activa. Se mantiene privado el repositorio.

El consumidor VM ya lee los tres objetos exactos mediante instance principal, verifica SHA-256 antes de `docker load` y comprueba el ID de contenido y `linux/amd64` después. Compose utiliza IDs locales `sha256:...` y `pull_policy: never`; no necesita credenciales GitHub ni registro. Su IAM permite solo esos objetos de release y su objeto de bootstrap. El rollback conserva esos IDs inmutables.

CI prepara archivos/manifiestos del candidato como artifacts privados. La preparación de una release estable privada inmutable está autorizada para la prueba nativa coordinada, y requiere seis assets exactos vinculados al código validado. Los artifacts `candidate` se rechazan como release instalable. Las pruebas locales del consumidor no sustituyen la aceptación del handoff real y del runtime OCI.
Perfil y clave OCI se entregan por el canal cifrado. El payload contiene exactamente `config`, `key`, `runtime_env` e `image_assets`; rechaza campos TLS externos. La VM genera y conserva una clave TLS RSA 3072 y un certificado autofirmado anual con SAN de su IP. Solo el PEM público canónico y su huella SHA-256 DER regresan por OCI Run Command autenticado. El hook verifica hostname y salud con un almacén TLS que contiene exclusivamente esa hoja, sin CAs del sistema ni proxy ambiental. El navegador requiere confianza explícita en esa hoja/IP antes de OIDC; el certificado no procede de una CA pública. La VM verifica identidad y fingerprint, instala archivos atómicos y consume la clave temporal; elimina el objeto mediante ETag y verifica su ausencia. Nunca se copia `.oci` del entorno de desarrollo. Los logs de callback OIDC no incluyen códigos en query strings.

## Recursos AIDP

`aidp/manifest.json` declara los tres programas legibles, sus fuentes de ensamblado y hashes, además de recursos que define el bootstrap. La publicación conserva `/Workspace/medallion/gods_eye_view/`, workflows social/sensor y cuatro computes separados. `publication_version` une consultas Gold, evidencia y acciones del mapa. SQLite es proyección reconstruible; Object Storage y Gold conservan los datos durables.

Instalación, tarea activa, publicación comprobada y conversación del agente son gates separados. Esta tarea no ejecutó inferencia ni escrituras cloud. Las pruebas de fábrica y fixtures no acreditan el runtime AIDP efectivo ni permisos de una instalación viva.
