Ajuste solicitado posterior: selector de Identity Domain para v1.0.2 en validación. `identity_domain_id` es select requerido con `options_source=oci_identity_domains` y patrón OCID; no se pide escribir el OCID. El consumidor/listado CTN y sus opciones reales son responsabilidad del coordinador. v1.0.1 se conserva inmutable.

# God’s Eye View: candidato para aceptación OCI

La corrección del primer arranque está publicada como [v1.0.1 privada e inmutable](https://github.com/jgangini/aidp-ai-gods-eye-view/releases/tag/v1.0.1), ID `436036581`, sin draft/prerelease. Código: `6605611c02ea79f1732044ea8305b8b6da322ed8`. [CI 42150688959](https://github.com/jgangini/aidp-ai-gods-eye-view/actions/runs/42150688959): seis jobs aprobados. [Recibo de seis assets, imágenes y hashes](../releases/v1.0.1.json).

La release anterior [v1.0.0](https://github.com/jgangini/aidp-ai-gods-eye-view/releases/tag/v1.0.0) se conserva inmutable con sus seis assets ([recibo](../releases/v1.0.0.json)). El cierre posterior en main solo modifica documentación. No se hicieron mutaciones OCI, inferencia ni actores pagados; instalación y aceptación reales corresponden al coordinador.

## Alcance y primer arranque

Destino independiente `D:/dev/codex-aidp-ai-gods-eye-view`, remoto privado `https://github.com/jgangini/aidp-ai-gods-eye-view`; visibilidad privada y permiso ADMIN verificados. Fuente congelada `3c82617fd298933995e954955841007253cc0985`: 417 archivos versionados extraídos con procedencia, sin `.oci`, estado ni caches. Requisitos: [diagnóstico de extracción](../migration-assessment.md) y contrato común del coordinador.

La única interfaz es el visor con controles integrados. API propia OIDC/RBAC, membresía/revocación y permisos AIDP efectivos USER/GROUP/ROLE; seleccionar administrador no cambia al operador firmante. Se conservan Gold, Object Storage/CAS, checkpoints, rutas Workspace y cuatro computes separados. Sin instalación HTTP, login local ni dependencia Autonomous.

Preflight selecciona imagen pública Oracle Linux 9 y AD compatibles con E5.Flex mediante paginación; conserva selecciones fijadas al reanudar. Calcula objeto/SHA del bundle del código verificado. Terraform deriva la URL y el callback OIDC de la IP pública asignada. Se retiraron campos manuales de dominio/origen, certificado/clave TLS, imagen/AD y objeto/hash del bundle. La capacidad efectiva de lanzamiento se debe aceptar en OCI.

La VM genera una clave TLS RSA 3072 local y hoja autofirmada anual con SAN IP. Solo PEM público canónico y huella SHA-256 DER salen por OCI Run Command autenticado. Health confía exclusivamente en esa hoja y comprueba IP/vigencia; no desactiva TLS ni usa proxy ambiental. **Browser requiere confianza explícita en esa hoja/IP antes de OIDC; no es una CA pública.** Renovación o cambio de IP requieren recuperación explícita.

Un único servicio systemd ejecuta recepción/activación cuando el runner lo inicia después de publicar el sobre cifrado. Resume funciona con clave temporal ya preparada; una entrega completada comprueba su identidad y termina sin esperar otra vez. El hook verifica los tres IDs del recibo activo antes de declarar éxito, evitando aprobar un rollback anterior.

El host fija protocolo V2 y una revisión que combina bundle y plantilla de arranque. Un host v1.0.0 o con otra revisión se rechaza antes de preparar el sobre/cargar imágenes. Updates de imágenes con esa misma revisión funcionan; cambios del bootstrap requieren migración/recuperación autorizada del host, sin prometer actualización automática de scripts mediante `user_data` ignorado. Se preservan los recursos/datos durables.

## Validación ejecutada

- Preflight: `scripts/arch-preflight.ps1`; baseline inicial vacío conservado (5 archivos, calidad 7780). Gate ya degradado antes de la corrección; no se sobrescribió.
- Postflight final: `scripts/arch-postflight.ps1`; **1671 passed, 6 skipped**, tres programas/manifiestos AIDP válidos, Terraform validate y **tres mocks** aprobados, incluido origen/callback de una IP asignada. El comando global termina con error por Sentrux.
- Foco de primer arranque: 63 aprobados, incluidos TLS SSL real por loopback, receptor generado, paginación/AD alternativo, Resume, rechazo de IDs antiguos y OpenSSL público sin clave anexada. Son un subconjunto, no cobertura sumada.
- CI: Python, Terraform, frontend y builds/paquetes de las tres imágenes aprobados sobre el SHA de v1.0.1. Controles: 89 tests/build React; visor: 119 tests/build nativo. Upstream y sus parches permanecen fijados.
- Parser/extractor CTN reales sobre el ZIP completo del commit: **46.611.182 bytes**, selección **88 archivos / 1.153.026 bytes**. Settings reales: **100 MiB / 250 archivos / 10 MiB extraídos**, sin ampliar límites. Manifiesto con seis assets por fase, 15 campos de formulario y nueve runtime fields aceptado.
- Imagen CTN existente, sin red y montando solo esos 88 archivos: imports de hooks/primer arranque/TLS y bundle aprobados. Bundle **22.709 bytes**, SHA `7fab22b0c20c405f79718b58b77071f64c99dd4d3c0c61ea0c7bc57bf44a4a7b`, idéntico al artifact CI. Revisión del host `77909c23cfa39ac899a9c04e817cd2290fee4ccdbc16f6bea2acf708c37737d5`.
- Release: tag→SHA exacto, privada, inmutable y seis assets remotos cuyos tamaños/digests coinciden con los bytes locales. Promoción modifica solo release en los JSON; conserva archivos, imagen/tag/ID. Consumidor real valida metadata/JSON/gzip publicados y staging CAS simulado/idempotente, sin OCI. El bundle es separado; no es séptimo asset.
- Graphify: no configurado; no se inicializó.
- Sentrux: **DEGRADED, no aprobado** frente al baseline inicial; calidad 7780→6606, complejidad 0→104, coupling 0→0.07; cero ciclos/archivos dominantes. Sin reglas propias. Referencia congelada del producto: calidad 6589 y 89 funciones complejas; no sustituye el baseline.
- Codex: GPT-6.1 Sol High -- aceptación OCI y recuperación. [Referencia](https://learn.chatgpt.com/docs/model-selection)

Seis skips: GIS con opt-in, cuatro comprobaciones Spark/JDK/Delta y Nginx local. Nginx se comprobó aparte realmente en Linux en la extracción; no se declara aceptación de la VM nativa. Persisten avisos npm heredados (un crítico y siete altos), con revisión del consumidor/regresiones documentadas; no audit limpio ni actualización del pin para ocultarlos.

Dos suites/archivos del instalador combinado permanecen como evidencia tras rechazo de auto-review a su borrado. No se reintentó eliminarlos; están excluidos de la aplicación/imagen. `apps/backend/tests/validation-scope.json` mantiene clasificación y sustitutos. No se declara aprobada toda la suite histórica. Arko guía responsabilidades, sin declarar `arko check` aprobado para este layout.

La revisión independiente acotada detectó y cerró omisiones de referencia, pin TLS, salida pública, selección/paginación, permisos y Resume; sin hallazgos abiertos en ese alcance. No se midieron ahorro ni tokens. Windows requirió escalación/temporales nuevos por ACLs; no se borraron corridas previas. Un intento inicial sin escalación falló y no se contó como check aprobado. Diff y escáner de secretos se ejecutan en el cierre; no leen `.oci` ni imprimen valores.

## Entrega al coordinador

Orden autorizado: Governance→Market→GodEye sobre **un solo AIDP**. Usar fuente `ref=v1.0.1`, SHA indicado y `release_tag=v1.0.1`; `aidp_mode=existing`, `existing_ai_data_platform_ocid` y `existing_workspace_key` iguales a los outputs exactos de la primera instalación. Dominio ACTIVE y administrador ACTIVE con permisos efectivos verificados. Esos OCID/key reales aún no se conocen en este candidato; no se inventan.

El coordinador conserva Browser, Docker compartido, colas y mutaciones OCI. La consulta real local a `trusted_deployment_project` sigue rechazando GodEye como no deployable: falta registrar/habilitar el catálogo e integrar/desplegar el handoff CTN en su entorno. [Contrato exacto de assets](../private-artifact-handoff.md), sin tokens GitHub en hooks/VM.

Pendientes: aceptación de IAM/roles, capacidad/arranque VM, confianza del certificado en Browser, instalación compartida/new-existing, recuperación, permisos negativos, task/publicación y conversación de la revisión instalada. Sin ampliar calidad de respuestas ni actores pagados. Sentrux y avisos heredados requieren revisión antes de producción.
