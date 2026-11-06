# Contratos del candidato

El ID del producto es `gods_eye_view`; el proyecto Deploy Studio es `aidp-ai-gods-eye-view`. Las identidades persistentes del dataset y Workspace se conservan. El inventario inicial describe la fuente; los archivos actuales y sus pruebas describen este candidato.

## Interfaz e identidad

La única interfaz está en `/gods-eye-view/`; abre los controles integrados `/controls/` para administradores. `/api/gods-eye-view/session` revalida cuenta y membresía; `/api/admin/session` exige además el `admin_user_ocid` seleccionado y permisos AIDP efectivos, incluidos grupos y roles heredados. La API rechaza headers de identidad externos como autorización y comprueba las mutaciones en servidor. OIDC utiliza callback `/api/auth/oci/callback`, PKCE, firma, issuer, audience, nonce y vigencia.

El gateway elimina headers aportados por el cliente. Node y el bridge carecen de puertos públicos. La API no expone instalación HTTP ni registro/login local. Las transacciones OIDC y límites son por proceso: una sola instancia/worker hasta implementar almacenamiento compartido.

## Instalación desde Deploy Studio

`terraform/deploy-studio.json` usa schema 1 y el selector común `oci_aidp_administrators`. Se validó con el modelo Pydantic y extractor de archivo reales de CloudTechNext, incluidos entrypoints e include_paths. Esa validación local no demuestra instalación cloud.

El usuario elige `identity_domain_id`, `admin_user_ocid`, `aidp_mode=new|existing` y, para existente, `existing_ai_data_platform_ocid` y `existing_workspace_key`. Los hooks vuelven a comprobar identidad/dominio/roles en instalación y Resume. La plataforma nueva concede explícitamente `AI_DATA_PLATFORM_ADMIN` al seleccionado y verifica el resultado. El operador conserva su propia identidad firmante; la selección no lo suplanta ni crea otro provisioner.

Las cuatro selecciones medallion y artifacts son distintas. Un catálogo externo requiere `existing_catalog_key` exacto; encontrar un nombre coincidente no autoriza adoptarlo. Los recursos externos no entran al state como recursos a destruir. Los recibos operativos usan CAS, identidad exacta y exclusión de runners.

La VM requiere Oracle Linux 9, capacidad del shape elegido, salida a repositorios de paquetes y a OCI, y un origen HTTPS con certificado/clave propios. La identidad de instancia solo lee el bundle fijado y consume el objeto cifrado de su despliegue. La política de servicio AIDP nueva se declara separadamente de las referencias externas. La propagación real de IAM queda por aceptar en OCI.

## Artefactos privados y secretos

El bootstrap de VM es un ZIP determinista de cuatro archivos públicos de aplicación: Compose, script de arranque, receptor cifrado y cargador de imágenes verificadas. Su SHA-256 y objeto `releases/...zip` se fijan en inputs no secretos. Post-apply verifica los bytes y los publica condicionalmente en el bucket artifacts. La VM los lee mediante instance principal y verifica el hash: no necesita PAT para descargar fuente GitHub ni clona repositorios privados al arrancar.

La entrega privada está **aislada y probada como componente**, y su integración al control plane sigue pendiente de la decisión de visibilidad. `scripts/deployment/image_assets.py` puede autenticar, validar tag/commit/repositorio/manifiestos y subir los archivos condicionalmente al bucket artifacts. Su API de pruebas recibe una credencial explícita, pero el manifiesto activo no pide ese token ni supone `GH_TOKEN`/`GITHUB_TOKEN` en los hooks: CloudTechNext filtra ese entorno.

Para repositorios privados, el coordinador debe ejecutar la descarga autenticada desde el control plane y entregar al runner una referencia protegida de los assets ya verificados. Ese contrato genérico no está implementado en este repositorio. El hook actual rechaza la falta de esa autorización/entrega; no se afirma que una instalación privada ya sea ejecutable. Si el usuario elige repositorios públicos, se podrá habilitar descarga HTTPS anónima con los mismos pins y hashes. No se cambió visibilidad ni se considera aprobada esa decisión.

El consumidor VM ya lee los tres objetos exactos mediante instance principal, verifica SHA-256 antes de `docker load` y comprueba el ID de contenido y `linux/amd64` después. Compose utiliza IDs locales `sha256:...` y `pull_policy: never`; no necesita credenciales GitHub ni registro. Su IAM permite solo esos objetos de release y su objeto de bootstrap. El rollback conserva esos IDs inmutables.

CI prepara archivos/manifiestos del candidato como artifacts privados, sin publicar una release. La aceptación nativa necesita resolver el handoff anterior y una release estable inmutable con los seis assets exactos. Los artifacts `candidate` no cumplen ese gate y se rechazan. Los tests del descargador y del cargador no sustituyen esa integración pendiente.
Certificado/clave TLS, perfil y clave OCI se entregan por ese mismo canal cifrado. La VM verifica identidad y fingerprint, instala archivos atómicos y consume la clave temporal; elimina el objeto mediante ETag y verifica su ausencia. Nunca se copia `.oci` del entorno de desarrollo. Los logs de callback OIDC no incluyen códigos en query strings.

## Recursos AIDP

`aidp/manifest.json` declara los tres programas legibles, sus fuentes de ensamblado y hashes, además de recursos que define el bootstrap. La publicación conserva `/Workspace/medallion/gods_eye_view/`, workflows social/sensor y cuatro computes separados. `publication_version` une consultas Gold, evidencia y acciones del mapa. SQLite es proyección reconstruible; Object Storage y Gold conservan los datos durables.

Instalación, tarea activa, publicación comprobada y conversación del agente son gates separados. Esta tarea no ejecutó inferencia ni escrituras cloud. Las pruebas de fábrica y fixtures no acreditan el runtime AIDP efectivo ni permisos de una instalación viva.
