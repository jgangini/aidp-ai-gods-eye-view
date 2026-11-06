# God’s Eye View: diagnóstico de separación

Fecha: 2026-11-05. Diagnóstico original de la primera fase, conservado como evidencia del corte. La implementación posterior autorizada y sus checks se registran en `docs/tasks/current.md`; las afirmaciones de ausencia de cambios de las secciones de diagnóstico corresponden a aquella fase. No se ejecutaron operaciones cloud ni una release final.

## Alcance y evidencia

Destino: `D:/dev/codex-aidp-ai-gods-eye-view`; repositorio solicitado: `jgangini/aidp-ai-gods-eye-view`.
Fuente congelada: `D:/dev/codex-oci-ai-data-platform-workbench-starter-kits`, commit `3c82617fd298933995e954955841007253cc0985` (v4.0.11 según encargo; HEAD verificado). Fuente limpia al inicio. No se ha escrito en ella.

El destino existía vacío, sin `.git`, remoto configurado, instrucciones locales ni `.oci`. `gh repo view jgangini/aidp-ai-gods-eye-view --json nameWithOwner,url,isPrivate,defaultBranchRef` falló inicialmente por proxy; la repetición con red habilitada llegó a GitHub y respondió `Could not resolve to a Repository`. Esto no distingue repositorio inexistente de falta de acceso. Existencia, visibilidad, permisos y rama remotos siguen **sin verificar**; no se ha creado repositorio, commit ni push. No se abrieron credenciales ni se copiaron estado, `.local`, `.oci`, caches o el monolito.

Leídos: `AGENTS.md`, `docs/README.md`, `docs/contracts.md`, `docs/development.md`, `docs/modules/ai-gods-eye-view.md`, implementación y contratos ejecutables indicados abajo. No hay `.codex/AGENTS.md` ni `.arko/project.json` en la fuente. El grafo existente declara commit `2adb89a4`, distinto de HEAD; se consultaron su reporte e índice solo como navegación, sin tratarlo como prueba actual ni actualizarlo. Se hizo una búsqueda Semble focalizada con exclusiones existentes; el código es la evidencia autoritativa.

Skills consultadas: Arko y su workflow; AIDP Agent Flow LangGraph y compatibilidad; OCI Workbench Deploy y workflow-map; Source Intake (no aplica su flujo `.source` a esta extracción de implementación estable). No se ejecutaron sus comandos live. La estructura de telecomunicaciones del ejemplo Workbench no redefine este producto. Security Best Practices y Threat Model se consultaron para delimitar el futuro cambio de exposición; esta fase no implementa ese cambio ni pretende sustituir una revisión de seguridad de la implementación.

El plan común `docs/module-repository-separation.md` no estaba presente al inicio y apareció durante el diagnóstico; se leyó completo al cierre. Este documento es el diagnóstico local subordinado a ese contrato de coordinación. Coincide en fases, VM con administración propia, RBAC, independencia del portal, Gold y prohibición de adopción implícita. Se ajustó la estructura propuesta a `apps/`. El contrato común agrega distinciones obligatorias Deploy/Resume/Update/Redeploy/Delete y recursos owned/external: el instalador extraído debe preservarlas con recibos CAS/lock. No hay discrepancia de alcance identificada. Deploy Studio y retirada del monolito pertenecen al coordinador.

Cambios concurrentes observados al cierre: la fuente muestra `M docs/README.md` y `?? docs/module-repository-separation.md`, coherentes con trabajo coordinador, sin cambios de implementación observados; este chat no los escribió ni revirtió. En el destino apareció `.oci` durante el trabajo; se verificó exclusivamente su presencia con `Test-Path`, sin listar/leer contenido ni utilizarla. Sigue sin `.git`. La presencia de credenciales no acredita permisos ni autoriza operación cloud.

## Resultado principal

No basta con copiar `modules/ai-gods-eye-view/`. Existen tres partes acopladas: API/control y capturador en backend central, UI de administración en frontend central y aplicación nativa en VM privada. Spark y el agente son programas AIDP separados. La propuesta traslada API/control, captura y configuración de streaming/proveedores a la única interfaz del producto, integrada al visor en su VM, conservando upstream y recursos AIDP válidos. Instalación, Resume, Update y Redeploy se ejecutan exclusivamente desde Deploy Studio; la VM no incorpora portal de instalación ni diálogo de despliegue. Es una propuesta, no comportamiento ya implementado.

Ninguno de los tres productos tendrá portal como Starter Kits. Governance y Market son paquetes Python CLI/hooks y artefactos AIDP, sin frontend, login local, API de portal, VM administrativa ni imagen de portal. GodEye es el único con interfaz y API/RBAC para operar su visor. Arko organiza responsabilidades Python; no impone FastAPI/React ni otro framework. GodEye puede reutilizar el stack existente solo para esa interfaz integrada.

## Inventario funcional y llamadores

Rutas relativas a la fuente congelada. El apéndice enumera los archivos seleccionados por Git; los grupos siguientes explican su tratamiento.

| Fuente | Tratamiento propuesto y dependencias |
| --- | --- |
| `apps/backend/app/modules/ai_gods_eye_view/runtime/` | Extraer completo el dominio y su suite; mantener controles, CAS, captura, publicaciones, consultas y recuperación. Revisar imports externos y ensamblado antes de reubicar. |
| `runtime/api.py:129-163` | Factory local/cloud, productor periódico y routers inyectados; dependen de `app.state.settings`, factories AIDP, identidad y sesión. Separar composition root del portal; no ejecutar dos productores durante el corte. |
| `runtime/cloud.py:29-44` | Configuración AIDP, Object Storage y proyección SQLite; conservar semántica de 409/503. SQLite es reconstruible, no fuente de verdad. |
| `runtime/{module,installation}.py` | Extraer instalador a paquete Python CLI/hooks invocado por Deploy Studio, con loader, recibos y propiedad exacta. Retirar sus rutas/botón de instalación de la interfaz del producto; conservar recuperación durable en el runner. |
| `runtime/{capture,sensor_capture,landing,x,scheduling}.py` | Captura y planificación; preservar slots, deduplicación, agotamiento y reanudación. Solo X tiene captura social real; las demás redes y sensores son sintéticos actualmente. |
| `runtime/{pipeline,sensor_pipeline,classification,correlation,sensors,core}.py` | Procesamiento y reglas compartidas con programas AIDP; ensamblar desde fuentes explícitas. |
| `runtime/{control_store,post_index,posts,store,local}.py` | CAS Object, diario/proyección y fixtures locales. No transformar fixtures en evidencia nativa. |
| `runtime/{synthetic_reset,sensor_reset,source_rules}.py` | Confirmación, UUID, revisión, ámbito y cancelación durable; mover UI y backend juntos. |
| `runtime/{agent,gold_reader,agent_gateway,runtime_secrets}.py` | LangGraph existente, consulta Gold y credencial OCI. Conservar SQL fijo/validación y publicación vinculada. |
| `runtime/{parameters,oci_provider,oci_voice,native_proxy,media,area,corpus}.py` | Proveedores, envelopes, proxy, contenido/contexto y geografía; revisar dependencias de configuración/identidad. |
| `apps/backend/app/api/{viewer_auth,viewer_identity}.py`, `app/security.py` | Extraer capacidades necesarias, no el portal completo. OIDC, sesión, identidad pública limitada, rate limit y permisos siguen siendo obligatorios. |
| `apps/backend/app/main.py:187-196,252-259,649` | Llamador de productor, factories y montaje. Alta/registro y concesión de lector también aparecen en `320-416,471-504,777`; el coordinador debe retirar sus dependencias solo después del corte. |
| `apps/backend/app/services/oci/{aidp,identity,contracts,credential_bootstrap}.py`, `app/config.py` | Auditar cierre real por capacidades; `aidp.py:23` importa helpers del módulo: hay dependencia inversa. No copiar la fachada completa con kits/Governance ni introducir dependencia runtime a sus repositorios. |
| `app/packages/{catalog,aidp}.py`, `catalog.json` | Conservar contrato de paquete, integridad y carga explícita; `catalog.py:23` registra `gods_eye_view`. No descubrir paquetes arbitrarios. |
| `apps/frontend/src/GodsEyeViewAdmin.tsx` y componentes relacionados | Reutilizar configuración social, sensores, horarios, revisiones, proveedores y limpieza dentro del visor. Imports directos en `:1-10`; tipos/cliente del API real, sin segunda aplicación de portal. |
| `apps/frontend/src/App.tsx:2805-3114` | Evidencia de Settings, instalación y enlace actuales. Retirar shell/registro/administración de kits; trasladar instalación y selección de administrador a Deploy Studio. Solo controles operativos pertinentes se integran al visor. |
| `apps/frontend/src/{GodsEyeViewModuleManager,LocalGodsEyeViewAccess}.tsx` | Evidencia que no se extrae como UI: instalación/reanudación pasan a Deploy Studio; login local de portal se retira. Fixtures de identidad para tests no crean una pantalla de login nueva. |
| `modules/ai-gods-eye-view/` | Visor nativo, bridge Python, provider runtime, upstream fijado, assets/licencias y tests. Dockerfile `:29-31` importa helpers del backend central: trasladar explícitamente `area`, `native_proxy`, `viewer_identity`. |
| `apps/backend/app/modules/ai_gods_eye_view/package/` | `lab.json`, notebooks, corpus social/sensor, manifests, imágenes y evaluación. Selección explícita por licencia y uso; hashes/versiones juntos. No copiar objetos de producción. |
| `terraform/hooks/gods_eye_{sources,agent_source,view_bootstrap}.py` | Renderizado de streams/agente y recursos. Reubicar sin copiar orquestación de otros módulos. |
| `terraform/h_gods_eye_view.tf`, `templatefile/gods_eye_view_user_data.sh` | Extraer intención de recursos del producto y dependencias; no es un root Terraform autosuficiente. Referencias VCN/buckets/identidad vienen del stack central. |
| `terraform/{b_variables,i_oci_identity,l_outputs}.tf`, `deploy-studio.json`, `hooks/post_apply.py` | Recortar contrato del producto con coordinador. Mantener schema v1/hooks y cierre de runner explícito; ningún cambio ahora. |
| `scripts/release/{gods_eye_view_release_update,load_release_image,vm_release_updater}.py`, CI/release y Docker/nginx | Reutilizar mecanismos por capacidad; updater/loader y gateway también forman parte del cierre, no solo visor. No copiar el updater central sin revisar dependencias. |

Componentes operativos candidatos a integrar al visor: `GodsEyeViewAdmin`, `GodsEyeViewPosts`, `GodsEyeViewSensors`, `GodsEyeViewSensorReadings`, `GodsEyeViewParameters`, `GodsEyeViewOciParameters`, `CaptureScheduleForm`, `SyntheticDataReset`, `ViewerIdentitySettings`, `godsEyeViewAdminState`, `gods-eye-view.css`. Reutilizar dependencias locales `LoadingIndicator`, `SearchableCombobox`, `SettingsConfirmation` y estilos imprescindibles según necesidad; conservar sus contratos sin reproducir Settings ni otro portal. `GodsEyeViewModuleManager` y `LocalGodsEyeViewAccess` permanecen solo como evidencia de flujos retirados/trasladados, incluidos en el apéndice para trazabilidad.

## API, identidad y frontera de red

Estado actual verificado: `runtime/access.py:27-50` verifica sesión y membresía actual, emite rol `reader` o `admin`; `api.py:159-163` separa routers. Las mutaciones de revisión/ubicación bajo `/api/gods-eye-view/*` pertenecen al router administrador (`:401-405`): el prefijo por sí solo no define permisos. OIDC conserva issuer, audience, firma, nonce, expiración y callback exacto. Transacciones y rate limits son por proceso: no escalar workers sin almacenamiento compartido verificado.

La VM actual no tiene IP pública y admite 8081 solo desde NSG proxy (`terraform/h_gods_eye_view.tf:52-59,78-108`). `server.py:73-76` acepta headers de identidad junto con presencia de cookie porque confía en ese perímetro; `:491-499` verifica admin contra VM1. No se ha identificado aquí un bypass del despliegue privado actual; publicar ese listener eliminaría una premisa necesaria.

**Decisión propuesta para instalaciones nuevas:** una VM de producto con entrada TLS 443 autenticada, visor con configuración integrada y API/control real para esa única interfaz; Node 4173, bridge/provider 8081 y endpoints internos solo loopback/red interna. Reutilizar FastAPI donde sirve a esa API, sin API de portal/instalación. Ninguna entrada pública a `/internal/`, proveedor o metadata. El gateway descarta headers de identidad externos y la API valida identidad y autorización en cada operación, sin confiar en una cookie meramente presente. Egreso controlado a Identity Domains, AIDP, Object Storage y proveedores explícitos. Mantener 8081 privado si se conserva gateway externo es una alternativa válida de menor cambio, pero debe seguir operando sin portal monolítico.

Roles reales: lector consulta snapshot/evidencia/capture-status y usa conversación autorizada; administrador configura fuentes, horarios, proveedores, revisiones, ubicación y limpieza. El rol debe proceder de membresía/privilegios verificados del producto para cuenta y entorno; conceder acceso lector nunca concede administración. Desacoplar `settings.admin_username` como única definición de admin exige contrato/test de RBAC, no solo ocultar botones. Revocación durante sesión abierta debe denegar la siguiente petición. Mantener rate limit, same-origin/CSRF para mutaciones, cookies HttpOnly/Secure y secretos solo servidor.

Conservar contratos operativos necesarios de `/api/gods-eye-view/*` y `/api/admin/gods-eye-view/*` en el origen del visor; exportar/revisar OpenAPI de esa API. `/gods-eye-view/` sirve la única interfaz; la antigua pantalla `/admin/gods-eye-view` aporta controles para integrar, no otro portal. Las rutas actuales de instalación y selección de administrador del portal se retiran del servicio de la VM y pasan al contrato Deploy Studio/CLI/hooks. No introducir aliases legacy. La concesión de acceso lector necesita autorización real de ámbito producto, separada de seleccionar al administrador de instalación. Nuevos callbacks/orígenes son cambios de configuración revisados, no redirects silenciosos.

## Estructura propuesta y AIDP

Usar Arko para responsabilidades y contratos Python del instalador y dominio; en GodEye también composition root, API/control y cliente de su visor. No impone FastAPI/React. No ejecutar `init` sobre este destino ya documentado. Preparar scaffolding revisable en una futura fase sin sobrescribir evidencia. El dominio existente se mantiene hasta disponer de tests del cierre.

```text
src/gods_eye_view/           # instalador CLI/hooks, dominio y adaptadores importables
apps/backend/app/            # identidad y API real exclusiva del visor
apps/frontend/               # controles integrados al visor; sin portal/instalador
viewer/                     # aplicación nativa/upstream/patches/build propio
aidp/manifest.json          # una sola declaración de assets/recursos/publicación
aidp/workspaces/default/files/10_bronze/{social_network,sensor_stream}.py
aidp/workspaces/default/files/20_silver/README.md
aidp/workspaces/default/files/30_gold/README.md
aidp/workspaces/default/files/40_report/ai_gods_eye_view.py
aidp/workspaces/default/{workflows,compute,agent_flow}/
aidp/master_catalog/        # definiciones verificadas derivadas del instalador
package/lab.json            # contrato versionado; no segunda implementación editable
terraform/                  # root nuevo y contrato existing, propietarios explícitos
scripts/                    # renderizado, release y única ruta de validación
docs/                       # este diagnóstico y contratos/operación del producto
```

El árbol es propuesta; no existe aún. `default` es alias local, no ID ni orden de crear otro workspace. Preservar destino nativo `/Workspace/medallion/gods_eye_view/`, tareas `social_network`, `sensor_stream`, workflows `wf_ai_gods_eye_view_social_network`, `wf_ai_gods_eye_view_sensor_stream` y computes `aidp_gods_eye_view_{social,sensor,query,agent}_compute`. Separar captura social/sensor, query Spark y agente AI. Pausar captura no detiene compute.

El agente ya importa `langgraph.prebuilt` (`runtime/agent.py:228-239`); adaptar su factory/hooks nativos para pruebas portables sin reescribir razonamiento. Mantener una fuente editable y ensamblado explícito legible: no loaders ocultos ni bundles codificados. Preservar `publication_version`, SQL parametrizado fijo, límites y evidencias; tablas/vistas `oci_gold.territorial_{incidents,evidence,sensors,event_posts}`, prefijos `04_gold/prisma/*` y `.control/prisma/agent.json` son identidades vigentes, no aliases a renombrar. Queries por AIDP Gold; ningún writer/reader nuevo en Autonomous.

Cuatro buckets medallion distintos más artifacts separado; controles `.control/gods_eye_view/` en bucket seleccionado explícitamente, no inferido de Landing. Preservar `AidpRuntime` OCI-only, identidad exacta y permisos por workspace/recurso. No cambiar las versiones instaladas para coincidir con una skill: contrastar locks y runtime TEST observado durante aceptación autorizada. No se ha comprobado compatibilidad nativa ni ejecutado inferencia.

## Infraestructura nueva y existente: propiedad y rollback

| Modalidad | Contrato propuesto |
| --- | --- |
| `new` | Root reproducible del producto; VCN/subnet o referencias explícitas, VM/gateway, IAM/OIDC, buckets y AIDP según selección. Declarar qué crea y qué reutiliza; no crear políticas/identidades duplicadas por defecto. Plan revisado con allowlist antes de aplicar. |
| `existing` | Solo referencias exactas y verificadas de stack, instalación, recurso, dueño y recibos actuales. Ninguna importación de estado, adopción por nombre ni reemplazo automático. Si no se puede demostrar propiedad, bloquear. |

La VM actual pertenece al Resource Manager stack original; dos raíces gestionando la misma VM/NSG/IAM producirían drift o destrucción. Independizar código no transfiere Terraform state. La transferencia, si se requiere, es operación futura del coordinador con inventario, backup protegido, planes de ambos lados sin destrucción/reemplazo y recuperación ensayada. Hasta entonces el propietario original conserva recursos; no aplicar un segundo stack sobre ellos. No eliminar el monolito ni su estado al terminar esta fase.

Brecha confirmada: `terraform/j_oci_ai_data_platform.tf:34` declara `oci_ai_data_platform_ai_data_platform.lab` sin condición `count`/`for_each` ni selector de plataforma existente. AIDP `new/existing` es capacidad nueva por implementar y probar, no una opción disponible por trasladar el Terraform actual. Una plataforma/workspace externos se referencian y verifican sin incorporarlos como recursos destruibles del stack producto.

Consumidor Deploy Studio verificado por lectura en `D:/dev/codex-cloudtechnext/app/backend/app/services/deployment_source.py`: `ManifestField:107-150`, `PostApplyContract:350`, `PreflightContract:383`, `DeploymentManifest:409` usan `extra="forbid"`. `options_source` no admite AIDP; no inventar ese valor ni claves nuevas. Primera versión compatible: `select` con opciones explícitas `new/existing`, OCID de tipo `text` con `visible_when`, validación exacta en preflight y `secret_inputs` separados para preflight/post-apply. El manifiesto futuro debe pasar el parser real; aquí no se generó ni se declaró validado uno. Descubrimiento dinámico de AIDP requeriría cambio genérico coordinado del consumidor.

La selección genérica del administrador pertenece al coordinador en CloudTechNext y es capacidad nueva del consumidor. El producto consume el ID estable verificado, nunca un correo/nombre como autorización ni un `options_source` inventado. Deploy Studio revalida server-side usuario activo, dominio, ámbito y roles efectivos antes de instalar y al Resume; cambiar destino invalida la selección previa. Con plataforma nueva comprueba elegibilidad de dominio antes del bootstrap y asignaciones efectivas después, antes de publicar recursos. Vincular administrador/ámbito al recibo de operación y conservarlo en Resume. Seleccionarlo no suplanta la identidad firmante del operador ni autoriza otro provisioner; no pedir contraseña admin local. El runtime del visor mantiene sus controles de acceso/revocación para operar, sin replicar este selector de instalación.

Para el corte futuro: registrar IDs/operaciones y revisiones sin exponer secretos; aislar candidato; detener escritores afectados antes de sustituir programas; confirmar ausencia de productor duplicado; transferir configuración protegida por canal autorizado (nunca Git); conservar checkpoints, diario, objetos y permisos. Activar consumidor solo tras publicación/versiones y tareas de revisión instalada verificadas. No resolver conflictos borrando controles ni renombrando recursos válidos.

Rollback de aplicación: imagen anterior saludable y configuración compatible, publicación conocida y recibo de operación conservados. Rollback del esquema/controles no se deduce del rollback de imagen; evitar cambio incompatible en la primera extracción. Detener candidato y restaurar un único productor; no reproducir lotes nuevos ni borrar progreso para aparentar recuperación. Callback/DNS/gateway y propiedad infra requieren plan de reversión coordinado separado.

## Upstream, CI y releases

Pin del visor: `bilawalsidhu/gods-eye-view` commit `aa16b7c3b0166a89d8c7a6089e0aff53a22faaee`, archive SHA-256 `a6020d0aa12a952585edee44a4765ab11f511e3f616927645d7ce04ce48487cb` (`upstream.json:2-5`). `prepare_upstream.py` valida archive, hashes y anclas únicas de los nueve parches. Mantener licencias/avisos y exclusiones de datos restringidos. El adaptador vendorizado posee procedencia distinta `b1a958242cfcd0a01cb68ea6035a1da037a58cfd`; no presentarlo como el pin nativo.

Build desplegado: Dockerfile Node 24.14.0, `npm ci --ignore-scripts`, tests y `node native/runtime.mjs --build`. `npm run build` aislado construye la página standalone retenida, no acredita el visor nativo. No clonar upstream ni `git pull main` al arrancar; bootstrap carga imagen inmutable verificada.

Propuesta CI: actualización upstream solo mediante PR que cambie commit, hash y parches verificables; comprobar licencias, tests nativos, build e integración API. La actualización automática puede proponer PR, nunca publicar una rama móvil. Release ligada al nuevo repo confiable, commit/digest/sha256, `linux/amd64` y assets canónicos versionados. Preservar protocolo loader/updater v1 donde corresponda; no falsificar recibos antiguos para cambiar repositorio. Validar imagen candidate, health y restauración de previous al fallar; conservar cache/config cifrada, usuario sin privilegios, filesystem readonly y capabilities eliminadas.

## Secuencia y criterios verificables antes de extraer/publicar

1. Reconciliar plan común, remoto y permisos; decidir modo de red y propietario de cada recurso con coordinador. Preparar instrucciones repo-local y una sola ruta preflight/postflight; no inicializar graphs como efecto secundario.
2. En la futura implementación capturar baseline con checks existentes adaptados; comprobar cierre de imports sin el monolito en `PYTHONPATH`, build Docker con contexto exclusivo del producto y ausencia de acceso a repos hermanos. Usar Arko para mapa/OpenAPI y revisar el diff de contratos antes de aceptarlo.
3. Trasladar dominio/API con regresión de CAS 409, integridad de diario, reconstrucción SQLite, paginación/búsqueda, dedup, agotamiento, fechas tardías y reset/cancelación por ámbito. Suite base: `apps/backend/tests/modules/ai_gods_eye_view/test_*.py`; compartir solo fixtures estrictamente requeridos y `conftest.py` revisado.
4. Integrar controles social/sensor/proveedores al visor, usando las suites pertinentes `apps/frontend/tests/gods-eye-view-*.test.mjs` como regresión de comportamiento. La suite module-manager es evidencia del flujo a trasladar a Deploy Studio, no requisito de conservar su diálogo. Añadir RBAC de API ejecutable, revocación abierta y falsificación de headers. Mantener revisión/ubicación admin aunque la URL parezca de lector. Verificar ausencia de portal, login local y endpoints de instalación propios; no sustituir denegación de API con tests de botones.
5. Build/test visor: `modules/ai-gods-eye-view/tests/*.test.mjs`, pruebas upstream, provider, proxy/nginx e identidad del backend. Rechazar hash inválido, archive traversal/links, anclas ambiguas; preservar cifrado, revisiones concurrentes y fallo atómico. Probar que bridge, Node y `/internal/` no sean accesibles desde entrada pública.
6. Renderizar tres programas AIDP legibles y ejecutar `scripts/modules/ai_gods_eye_view/render_gods_eye_view_runtime.py --check`; actualizar versiones/hashes de manifiesto sobre bytes empaquetados. Tests `terraform/tests/test_gods_eye{_sources,_agent_source,_view_bootstrap,_view_infrastructure}.py` adaptados sin debilitar invariantes. No imponer el layout de otro producto.
7. Terraform fmt/validate/test con proveedor mock, incluyendo new/existing, referencias exactas y rechazo de plan destructivo/no permitido. Python 3.12/backend y Node 22/frontend central son baseline CI de origen, no obligación de recrear un portal; visor usa su Node fijado. Validar CLI/hooks desde Deploy Studio, Resume con administrador revalidado y rechazo de ID manipulado, usuario inactivo, dominio ajeno o roles insuficientes. Comprobar asignaciones post-bootstrap para AIDP nuevo. No introducir dependencia Autonomous al recortar requirements.
8. Antes del primer cambio source no trivial usar Sentrux baseline/gate y reglas existentes por una sola ruta; Graphify solo actualizar si ya existe grafo pertinente. Postflight tras última edición y documentar checks indisponibles.
9. Aceptación nativa posterior y autorizada: identidad OCI, permisos negativos/positivos, versiones runtime observadas, tareas de revisión exacta, Gold/snapshot/puntero y conversación con evidencia de esa publicación. HTTP 202, RUNNING, ACTIVE o respuesta plausible no bastan. Sin actores de pago, inferencia o compute nuevo dentro de esta fase.
10. Ensayar caída de candidate y rollback de imagen/config/gateway sin perder operaciones ni iniciar dos writers. Cortar dependencia del portal con todos sus servicios ausentes en entorno aislado; solo entonces coordinador decide retirada.

## Validación efectuada y límites

- Preflight/postflight: no ejecutados; diagnóstico y Markdown únicamente, destino sin Git. No se crearon wrappers ni scaffolding para un reporte.
- Checks efectuados: cwd y existencia destino; Git local ausente; `.oci` ausente inicialmente y presente al cierre por `Test-Path`; HEAD y `git status --short` fuente; listado de archivos del commit; lectura estática de rutas/callers/tests; una búsqueda Semble. Consulta remota GH: proxy fallido y luego respuesta de repositorio no resoluble con red habilitada. Validación documental: 164 paths del apéndice pertenecen al commit y sin duplicados; cambios documentales concurrentes del coordinador observados en fuente. No se han ejecutado suites, builds ni pruebas de aplicación/cloud.
- Graphify: reporte/índice leídos, obsoletos respecto a fuente congelada; no actualizado por fuente solo lectura y cambio documental.
- Sentrux: no ejecutado; no corresponde gate source a este reporte documental ni escanear carpeta vacía.
- Codex: GPT-6.1 Sol Medium -- extracción coordinada con contratos, permisos y recuperación. [Referencia](https://learn.chatgpt.com/docs/model-selection)
- Revisión delegada: una exploración de visor/red/build, solo lectura; aportó dependencias Docker externas y confianza en proxy que condicionan extracción. Principal integró resultados con API/UI/AIDP. No hubo implementación paralela ni rework; tiempos/tokens de agente no disponibles. Sin comparación de rendimiento ni afirmación de ahorro.
- Pendientes: remoto, recibos/estado cloud, identidad viva, runtime TEST, capacidad/costes y autenticación real no verificados; no se infieren desde fixtures. No se tomaron screenshots ni se abrió UI.

## Apéndice: archivos de extracción a revisar

Listado del árbol Git congelado, sin copiar contenidos. Incluye dominios, UI, tests y hooks seleccionados; los servicios compartidos descritos arriba requieren recorte por capacidad, no extracción ciega. Es inventario de candidatos, no prueba de cierre transitivo completo.

Total de archivos enumerados: 164

```text
apps/backend/app/modules/ai_gods_eye_view/runtime/__init__.py
apps/backend/app/modules/ai_gods_eye_view/runtime/access.py
apps/backend/app/modules/ai_gods_eye_view/runtime/agent_gateway.py
apps/backend/app/modules/ai_gods_eye_view/runtime/agent.py
apps/backend/app/modules/ai_gods_eye_view/runtime/api.py
apps/backend/app/modules/ai_gods_eye_view/runtime/area.py
apps/backend/app/modules/ai_gods_eye_view/runtime/capture.py
apps/backend/app/modules/ai_gods_eye_view/runtime/classification.py
apps/backend/app/modules/ai_gods_eye_view/runtime/cloud.py
apps/backend/app/modules/ai_gods_eye_view/runtime/control_store.py
apps/backend/app/modules/ai_gods_eye_view/runtime/core.py
apps/backend/app/modules/ai_gods_eye_view/runtime/corpus.py
apps/backend/app/modules/ai_gods_eye_view/runtime/correlation.py
apps/backend/app/modules/ai_gods_eye_view/runtime/gold_reader.py
apps/backend/app/modules/ai_gods_eye_view/runtime/installation.py
apps/backend/app/modules/ai_gods_eye_view/runtime/landing.py
apps/backend/app/modules/ai_gods_eye_view/runtime/local.py
apps/backend/app/modules/ai_gods_eye_view/runtime/media.py
apps/backend/app/modules/ai_gods_eye_view/runtime/module.py
apps/backend/app/modules/ai_gods_eye_view/runtime/native_proxy.py
apps/backend/app/modules/ai_gods_eye_view/runtime/oci_provider.py
apps/backend/app/modules/ai_gods_eye_view/runtime/oci_voice.py
apps/backend/app/modules/ai_gods_eye_view/runtime/parameters.py
apps/backend/app/modules/ai_gods_eye_view/runtime/pipeline.py
apps/backend/app/modules/ai_gods_eye_view/runtime/post_index.py
apps/backend/app/modules/ai_gods_eye_view/runtime/posts.py
apps/backend/app/modules/ai_gods_eye_view/runtime/runtime_secrets.py
apps/backend/app/modules/ai_gods_eye_view/runtime/scheduling.py
apps/backend/app/modules/ai_gods_eye_view/runtime/sensor_capture.py
apps/backend/app/modules/ai_gods_eye_view/runtime/sensor_pipeline.py
apps/backend/app/modules/ai_gods_eye_view/runtime/sensor_reset.py
apps/backend/app/modules/ai_gods_eye_view/runtime/sensors.py
apps/backend/app/modules/ai_gods_eye_view/runtime/source_rules.py
apps/backend/app/modules/ai_gods_eye_view/runtime/store.py
apps/backend/app/modules/ai_gods_eye_view/runtime/synthetic_reset.py
apps/backend/app/modules/ai_gods_eye_view/runtime/x.py
apps/backend/tests/modules/ai_gods_eye_view/__init__.py
apps/backend/tests/modules/ai_gods_eye_view/test_gods_eye_native_proxy.py
apps/backend/tests/modules/ai_gods_eye_view/test_gods_eye_upstream.py
apps/backend/tests/modules/ai_gods_eye_view/test_gods_eye_view_access.py
apps/backend/tests/modules/ai_gods_eye_view/test_gods_eye_view_agent_tools.py
apps/backend/tests/modules/ai_gods_eye_view/test_gods_eye_view_agent.py
apps/backend/tests/modules/ai_gods_eye_view/test_gods_eye_view_area.py
apps/backend/tests/modules/ai_gods_eye_view/test_gods_eye_view_bridge.py
apps/backend/tests/modules/ai_gods_eye_view/test_gods_eye_view_capture_schedule.py
apps/backend/tests/modules/ai_gods_eye_view/test_gods_eye_view_capture.py
apps/backend/tests/modules/ai_gods_eye_view/test_gods_eye_view_classification.py
apps/backend/tests/modules/ai_gods_eye_view/test_gods_eye_view_cloud.py
apps/backend/tests/modules/ai_gods_eye_view/test_gods_eye_view_compatibility.py
apps/backend/tests/modules/ai_gods_eye_view/test_gods_eye_view_context.py
apps/backend/tests/modules/ai_gods_eye_view/test_gods_eye_view_control_store.py
apps/backend/tests/modules/ai_gods_eye_view/test_gods_eye_view_corpus.py
apps/backend/tests/modules/ai_gods_eye_view/test_gods_eye_view_correlation_context.py
apps/backend/tests/modules/ai_gods_eye_view/test_gods_eye_view_credentials.py
apps/backend/tests/modules/ai_gods_eye_view/test_gods_eye_view_geography.py
apps/backend/tests/modules/ai_gods_eye_view/test_gods_eye_view_gold_reader.py
apps/backend/tests/modules/ai_gods_eye_view/test_gods_eye_view_installation.py
apps/backend/tests/modules/ai_gods_eye_view/test_gods_eye_view_media.py
apps/backend/tests/modules/ai_gods_eye_view/test_gods_eye_view_membership_api.py
apps/backend/tests/modules/ai_gods_eye_view/test_gods_eye_view_module.py
apps/backend/tests/modules/ai_gods_eye_view/test_gods_eye_view_object_post_index.py
apps/backend/tests/modules/ai_gods_eye_view/test_gods_eye_view_oci_provider.py
apps/backend/tests/modules/ai_gods_eye_view/test_gods_eye_view_oci_voice.py
apps/backend/tests/modules/ai_gods_eye_view/test_gods_eye_view_parameters.py
apps/backend/tests/modules/ai_gods_eye_view/test_gods_eye_view_pipeline.py
apps/backend/tests/modules/ai_gods_eye_view/test_gods_eye_view_post_pagination.py
apps/backend/tests/modules/ai_gods_eye_view/test_gods_eye_view_post_search.py
apps/backend/tests/modules/ai_gods_eye_view/test_gods_eye_view_posts.py
apps/backend/tests/modules/ai_gods_eye_view/test_gods_eye_view_provider_probes.py
apps/backend/tests/modules/ai_gods_eye_view/test_gods_eye_view_python_tasks.py
apps/backend/tests/modules/ai_gods_eye_view/test_gods_eye_view_queries.py
apps/backend/tests/modules/ai_gods_eye_view/test_gods_eye_view_read_performance.py
apps/backend/tests/modules/ai_gods_eye_view/test_gods_eye_view_reset_cancelled.py
apps/backend/tests/modules/ai_gods_eye_view/test_gods_eye_view_runtime_mode.py
apps/backend/tests/modules/ai_gods_eye_view/test_gods_eye_view_sensor_families.py
apps/backend/tests/modules/ai_gods_eye_view/test_gods_eye_view_sensor_pipeline.py
apps/backend/tests/modules/ai_gods_eye_view/test_gods_eye_view_sensor_recovery.py
apps/backend/tests/modules/ai_gods_eye_view/test_gods_eye_view_sensor_reset_all.py
apps/backend/tests/modules/ai_gods_eye_view/test_gods_eye_view_sensor_reset.py
apps/backend/tests/modules/ai_gods_eye_view/test_gods_eye_view_sensor_schedule.py
apps/backend/tests/modules/ai_gods_eye_view/test_gods_eye_view_sensors.py
apps/backend/tests/modules/ai_gods_eye_view/test_gods_eye_view_source_reads.py
apps/backend/tests/modules/ai_gods_eye_view/test_gods_eye_view_streaming.py
apps/backend/tests/modules/ai_gods_eye_view/test_gods_eye_view_synthetic_reset_api.py
apps/backend/tests/modules/ai_gods_eye_view/test_gods_eye_view_synthetic_reset_local.py
apps/backend/tests/modules/ai_gods_eye_view/test_gods_eye_view_synthetic_reset.py
apps/backend/tests/modules/ai_gods_eye_view/test_gods_eye_view_user_creation.py
apps/backend/tests/modules/ai_gods_eye_view/test_gods_eye_view.py
apps/backend/tests/modules/ai_gods_eye_view/test_identity_gods_eye_view.py
apps/backend/tests/modules/ai_gods_eye_view/test_native_provider_runtime.py
apps/backend/tests/modules/ai_gods_eye_view/test_viewer_auth.py
apps/backend/tests/modules/ai_gods_eye_view/test_viewer_identity_proxy.py
apps/backend/tests/modules/ai_gods_eye_view/test_viewer_identity.py
apps/backend/tests/modules/ai_gods_eye_view/test_viewer_nginx.py
apps/frontend/src/CaptureScheduleForm.tsx
apps/frontend/src/gods-eye-view.css
apps/frontend/src/GodsEyeViewAdmin.tsx
apps/frontend/src/godsEyeViewAdminState.ts
apps/frontend/src/GodsEyeViewModuleManager.tsx
apps/frontend/src/GodsEyeViewOciParameters.tsx
apps/frontend/src/GodsEyeViewParameters.tsx
apps/frontend/src/GodsEyeViewPosts.tsx
apps/frontend/src/GodsEyeViewSensorReadings.tsx
apps/frontend/src/GodsEyeViewSensors.tsx
apps/frontend/src/LocalGodsEyeViewAccess.tsx
apps/frontend/src/SyntheticDataReset.tsx
apps/frontend/src/ViewerIdentitySettings.tsx
apps/frontend/tests/gods-eye-view-admin.test.mjs
apps/frontend/tests/gods-eye-view-module-manager.test.mjs
apps/frontend/tests/gods-eye-view-parameters.test.mjs
apps/frontend/tests/gods-eye-view-reset.test.mjs
apps/frontend/tests/gods-eye-view-sensor-readings.test.mjs
apps/frontend/tests/gods-eye-view-sensors.test.mjs
modules/ai-gods-eye-view/.gitattributes
modules/ai-gods-eye-view/context_layers.py
modules/ai-gods-eye-view/Dockerfile
modules/ai-gods-eye-view/index.html
modules/ai-gods-eye-view/native/analyst.js
modules/ai-gods-eye-view/native/captureRefresh.js
modules/ai-gods-eye-view/native/entrypoint.py
modules/ai-gods-eye-view/native/godsEyeViewLayer.js
modules/ai-gods-eye-view/native/main.js
modules/ai-gods-eye-view/native/ociVoice.js
modules/ai-gods-eye-view/native/provider_runtime.py
modules/ai-gods-eye-view/native/providerSettings.js
modules/ai-gods-eye-view/native/runtime.mjs
modules/ai-gods-eye-view/native/sensorsLayer.js
modules/ai-gods-eye-view/native/styles.css
modules/ai-gods-eye-view/native/vite.config.mjs
modules/ai-gods-eye-view/native/voiceAudio.js
modules/ai-gods-eye-view/package-lock.json
modules/ai-gods-eye-view/package.json
modules/ai-gods-eye-view/prepare_upstream.py
modules/ai-gods-eye-view/provider_probes.py
modules/ai-gods-eye-view/README.md
modules/ai-gods-eye-view/requirements.txt
modules/ai-gods-eye-view/scripts/copy-assets.mjs
modules/ai-gods-eye-view/server.py
modules/ai-gods-eye-view/src/chat.js
modules/ai-gods-eye-view/src/context.js
modules/ai-gods-eye-view/src/imagery.js
modules/ai-gods-eye-view/src/main.js
modules/ai-gods-eye-view/src/model.js
modules/ai-gods-eye-view/src/style.css
modules/ai-gods-eye-view/tests/native-api.test.mjs
modules/ai-gods-eye-view/tests/native-browser-config.test.mjs
modules/ai-gods-eye-view/tests/native-catalog.test.mjs
modules/ai-gods-eye-view/tests/native-overlay.test.mjs
modules/ai-gods-eye-view/tests/native-sensors.test.mjs
modules/ai-gods-eye-view/tests/native-voice.test.mjs
modules/ai-gods-eye-view/tests/viewer.test.mjs
modules/ai-gods-eye-view/upstream.json
modules/ai-gods-eye-view/vite.config.js
scripts/modules/ai_gods_eye_view/evaluate_gods_eye_view_corpus.py
scripts/modules/ai_gods_eye_view/render_gods_eye_view_runtime.py
scripts/modules/ai_gods_eye_view/smoke_gods_eye_view_dom.mjs
scripts/modules/ai_gods_eye_view/smoke_gods_eye_view_local.py
terraform/hooks/gods_eye_agent_source.py
terraform/hooks/gods_eye_sources.py
terraform/hooks/gods_eye_view_bootstrap.py
terraform/tests/test_gods_eye_agent_source.py
terraform/tests/test_gods_eye_sources.py
terraform/tests/test_gods_eye_view_bootstrap.py
terraform/tests/test_gods_eye_view_infrastructure.py
```

Adicionalmente, package/ completo se inventaría mediante el árbol congelado; contiene fixtures, media, notebooks y manifests, sujetos a hashes/licencias. public/brand-icons y vendor/ conservan íntegros sus avisos, procedencias y assets permitidos. No se enumeran aquí individualmente las muestras del corpus.
