# Registro de validación de la release

Este archivo conserva evidencia histórica de validación, no instrucciones de instalación. El repositorio y sus releases son públicos; la [revisión de publicación](../evidence/publication-review.md) registra el alcance. Para funcionamiento actual, consultar [README](../../README.md), [contratos](../contracts.md) y [operación](../operations.md). Los límites de aceptación aquí descritos no equivalen a una comprobación nueva del entorno OCI.

## Cinco buckets independientes v2.1.0 publicado

Fuente `ca0c4a5dbfd8614c5aacfc03aaf3b62419038a33`, [PR #1](https://github.com/jgangini/aidp-ai-gods-eye-view/pull/1), [CI 42272619772](https://github.com/jgangini/aidp-ai-gods-eye-view/actions/runs/42272619772) con seis jobs aprobados. Artifacts y las cuatro capas Medallion tienen modos new/existing independientes, textbox nuevo y selector OCI; no hay control global ni fallback. Se conservan direcciones Terraform y `prevent_destroy`, se verifica región/compartimento y se comparan nombres/modos contra outputs antes del journal. El acceso sigue por OCI OIDC y OCI Run Command, sin cuenta local ni credenciales SSH nuevas.

Postflight: 1948 passed, seis skips y ocho mocks Terraform aprobados. Sentrux sigue DEGRADED, con calidad 6610→6620; Graphify existente actualizado a 3993 nodos/11388 aristas y wiki renovada, con límite HCL documentado. El coordinador reportó parser estricto y SSR all-new/all-existing aprobados, ocho grupos y 23 campos. También verificó Browser local con v2.1.0 y defaults reiniciados: cinco filas alineadas de modo/nombre, valores `oci_*` esperados, sin control global ni checkbox y campos bloqueados hasta validación OCI. Caché de releases renovada y health local `ok=true`, sin screenshots ni operaciones OCI. [Evidencia completa](../evidence/individual-bucket-ownership.md).

La [release v2.1.0](https://github.com/jgangini/aidp-ai-gods-eye-view/releases/tag/v2.1.0), ID `436861738`, fue publicada por el coordinador tras la aprobación explícita del usuario. API y tag confirman `draft=false`, `immutable=true`, latest y commit `ca0c4a5dbfd8614c5aacfc03aaf3b62419038a33`; acceso API anónimo HTTP 200 y los seis IDs, tamaños y hashes verificados sin cambios. El [recibo publicado](../releases/v2.1.0-candidate.json) conserva su nombre original y el antecedente del rechazo inicial, ya resuelto con esa aprobación. Handoff/CAS simulado aprobado; aceptación OCI y conversación del agente pendientes. Desde este chat no se modificaron OCI ni recursos compartidos.

## Formulario alineado con Governance v2.0.1 publicado

Fuente `68412c3c609b8b140224e863477873cb49e947b5`, [PR #1](https://github.com/jgangini/aidp-ai-gods-eye-view/pull/1), [CI 42262217605](https://github.com/jgangini/aidp-ai-gods-eye-view/actions/runs/42262217605) con seis jobs aprobados. Grupos Governance, 14 combobox/textbox, selectores AIDP/workspace/modelo, nombre AIDP con default `aidp_gods_eye_view`, bucket mode booleano, imagen local CTN y descripción inglesa de 321 caracteres con el enlace original. Tag y prefijo operativos quedan internos, con binding y conservación en Resume.

Postflight final: 1701 passed, seis skips, cuatro mocks Terraform y artefactos AIDP aprobados. Sentrux conserva el fallo histórico sin degradación adicional; Graphify sigue bajo responsabilidad del coordinador. El coordinador reportó SSR y Browser local v2.0.1 satisfactorios: imagen completa, enlace clicable, grupos correctos, default esperado, descripción de seis líneas y cero checkboxes. La aceptación OCI corresponde al coordinador. [Evidencia completa](../evidence/deploy-studio-governance-form.md).

La [release v2.0.1](https://github.com/jgangini/aidp-ai-gods-eye-view/releases/tag/v2.0.1), ID `436798697`, se publicó tras la aprobación explícita del usuario para el paquete exacto. API y tag confirman `draft=false`, `immutable=true` y SHA `68412c3c609b8b140224e863477873cb49e947b5`. Los seis IDs, tamaños y hashes coinciden con el paquete aprobado; acceso API anónimo HTTP 200 confirmado. El handoff/CAS simulado pasó desde un contexto sin campos operativos. El [recibo publicado](../releases/v2.0.1-candidate.json) conserva su nombre de archivo original; las releases anteriores permanecen intactas.

## Formulario completo v2.0.0 publicado

El [PR #1](https://github.com/jgangini/aidp-ai-gods-eye-view/pull/1) utiliza `schema_version: 2` y grupos JSON completos sobre `f74fb0b2f8fa675b186f03e9e1839970d2937b62`. Región tiene `span: 2` encima de los controles de compartimento. [CI 42224278241](https://github.com/jgangini/aidp-ai-gods-eye-view/actions/runs/42224278241) aprobó seis jobs; postflight final: 1700 passed, seis skips y tres mocks Terraform aprobados. Sentrux conserva el fallo histórico; Graphify se consultó y su actualización queda al coordinador.

La [release v2.0.0](https://github.com/jgangini/aidp-ai-gods-eye-view/releases/tag/v2.0.0), ID `436528205`, está publicada e inmutable tras la aprobación explícita del usuario y la publicación desde el coordinador. API y tag confirman `draft=false`, `immutable=true` y SHA `f74fb0b2f8fa675b186f03e9e1839970d2937b62`; los seis IDs, tamaños y hashes coinciden con el borrador verificado. El handoff/CAS simulado está aprobado. El [recibo publicado](../releases/v2.0.0-candidate.json) conserva su nombre de archivo original; la [evidencia completa](../evidence/deploy-studio-form-schema2.md) distingue publicación de aceptación OCI. Las pruebas de instalación requieren el motor CTN exclusivo de schema 2 y corresponden al coordinador.

## Compatibilidad del runner v1.0.3

Commit `6cf5814ca8c5dc44ab0b2333473c4745e3871a49`, [CI 42168548647](https://github.com/jgangini/aidp-ai-gods-eye-view/actions/runs/42168548647) con seis jobs aprobados y release ID `436133209` con seis assets verificados. El coordinador la publicó después del rechazo inicial desde el chat con autorización directa: [v1.0.3 pública e inmutable](https://github.com/jgangini/aidp-ai-gods-eye-view/releases/tag/v1.0.3), con [recibo publicado](../releases/v1.0.3.json). Conserva su manifiesto schema 1; las releases anteriores permanecen intactas.

El ajuste corrige los contextos pre/post de compartimento, declara los outputs consumidos tras el filtro CTN y verifica catálogo externo/recibo propio antes de APPLY. Postflight: 1699 passed, seis skips, tres mocks Terraform aprobados; Sentrux sigue DEGRADED y no se sobrescribió su baseline. La [evidencia del runner](../evidence/deploy-studio-runner-contract.md) y el [recibo del candidato](../releases/v1.0.3-candidate.json) distinguen checks locales/CI de aceptación OCI pendiente. No ejecutar el borrador como release estable.

## Release publicada anterior

La corrección del primer arranque está publicada como [v1.0.2 pública e inmutable](https://github.com/jgangini/aidp-ai-gods-eye-view/releases/tag/v1.0.2), ID `436043929`, sin draft/prerelease. Código: `730866e381d7573b9e40ab1badd1b152870de816`. [CI 42152185322](https://github.com/jgangini/aidp-ai-gods-eye-view/actions/runs/42152185322): seis jobs aprobados. [Recibo de seis assets, imágenes y hashes](../releases/v1.0.2.json).

La release anterior [v1.0.0](https://github.com/jgangini/aidp-ai-gods-eye-view/releases/tag/v1.0.0) se conserva inmutable con sus seis assets ([recibo](../releases/v1.0.0.json)). También se conserva [v1.0.1](https://github.com/jgangini/aidp-ai-gods-eye-view/releases/tag/v1.0.1), con su [recibo](../releases/v1.0.1.json), pública e inmutable. El cierre posterior en main solo modifica documentación. No se hicieron mutaciones OCI, inferencia ni actores pagados; instalación y aceptación reales corresponden al coordinador.

## Alcance y primer arranque

Destino independiente `D:/dev/codex-aidp-ai-gods-eye-view`, remoto público `https://github.com/jgangini/aidp-ai-gods-eye-view`; visibilidad pública y permiso ADMIN verificados. Fuente congelada `3c82617fd298933995e954955841007253cc0985`: 417 archivos versionados extraídos con procedencia, sin `.oci`, estado ni caches. Requisitos: [diagnóstico de extracción](../migration-assessment.md) y contrato común del coordinador.

Identity Domain usa ahora selector requerido `oci_identity_domains`, valor OCID y patrón preservado. El modelo Pydantic CTN real lo acepta; el contrato del consumidor lista dominios ACTIVE por nombre/compartimento en región home. Opciones reales y Browser corresponden al coordinador. No se vuelve a pedir un OCID manual. Fichas AIDP AI y PNG sin cambios.

La única interfaz es el visor con controles integrados. API propia OIDC/RBAC, membresía/revocación y permisos AIDP efectivos USER/GROUP/ROLE; seleccionar administrador no cambia al operador firmante. Se conservan Gold, Object Storage/CAS, checkpoints, rutas Workspace y cuatro computes separados. Sin instalación HTTP, login local ni dependencia Autonomous.

Preflight selecciona imagen pública Oracle Linux 9 y AD compatibles con E5.Flex mediante paginación; conserva selecciones fijadas al reanudar. Calcula objeto/SHA del bundle del código verificado. Terraform deriva la URL y el callback OIDC de la IP pública asignada. Se retiraron campos manuales de dominio DNS/origen, certificado/clave TLS, imagen/AD y objeto/hash del bundle. La capacidad efectiva de lanzamiento se debe aceptar en OCI.

La VM genera una clave TLS RSA 3072 local y hoja autofirmada anual con SAN IP. Solo PEM público canónico y huella SHA-256 DER salen por OCI Run Command autenticado. Health confía exclusivamente en esa hoja y comprueba IP/vigencia; no desactiva TLS ni usa proxy ambiental. **Browser requiere confianza explícita en esa hoja/IP antes de OIDC; no es una CA pública.** Renovación o cambio de IP requieren recuperación explícita.

Un único servicio systemd ejecuta recepción/activación cuando el runner lo inicia después de publicar el sobre cifrado. Resume funciona con clave temporal ya preparada; una entrega completada comprueba su identidad y termina sin esperar otra vez. El hook verifica los tres IDs del recibo activo antes de declarar éxito, evitando aprobar un rollback anterior.

El host fija protocolo V2 y una revisión que combina bundle y plantilla de arranque. Un host v1.0.0 o con otra revisión se rechaza antes de preparar el sobre/cargar imágenes. Updates de imágenes con esa misma revisión funcionan; cambios del bootstrap requieren migración/recuperación autorizada del host, sin prometer actualización automática de scripts mediante `user_data` ignorado. Se preservan los recursos/datos durables.

## Validación ejecutada

- Preflight: `scripts/arch-preflight.ps1`; baseline inicial vacío conservado (5 archivos, calidad 7780). Gate ya degradado antes de la corrección; no se sobrescribió.
- Postflight final: `scripts/arch-postflight.ps1`; **1672 passed, 6 skipped**, tres programas/manifiestos AIDP válidos, Terraform validate y **tres mocks** aprobados, incluido origen/callback de una IP asignada. El comando global termina con error por Sentrux.
- Foco ejecutado en v1.0.1 (código sin cambios): 63 aprobados, incluidos TLS SSL real por loopback, receptor generado, paginación/AD alternativo, Resume, rechazo de IDs antiguos y OpenSSL público sin clave anexada. Son un subconjunto, no cobertura sumada.
- CI: Python, Terraform, frontend y builds/paquetes de las tres imágenes aprobados sobre el SHA de v1.0.2. Controles: 89 tests/build React; visor: 119 tests/build nativo. Upstream y sus parches permanecen fijados.
- Parser/extractor CTN reales sobre el ZIP completo del commit: **46.612.450 bytes**, selección **88 archivos / 1.153.132 bytes**. Settings reales: **100 MiB / 250 archivos / 10 MiB extraídos**, sin ampliar límites. Manifiesto con seis assets por fase, 15 campos de formulario y nueve runtime fields aceptado.
- Comparación exacta de los 88 archivos seleccionados con v1.0.1: solo cambia el manifiesto Deploy Studio. Los hooks/primer arranque/TLS son byteidénticos a los importados en la imagen CTN existente sin red; el bundle de CI confirma sus mismos bytes/hash. Bundle **22.709 bytes**, SHA `7fab22b0c20c405f79718b58b77071f64c99dd4d3c0c61ea0c7bc57bf44a4a7b`, idéntico al artifact CI. Revisión del host `77909c23cfa39ac899a9c04e817cd2290fee4ccdbc16f6bea2acf708c37737d5`.
- Release: tag→SHA exacto, pública, inmutable y seis assets remotos cuyos tamaños/digests coinciden con los bytes locales. Promoción modifica solo release en los JSON; conserva archivos, imagen/tag/ID. Consumidor real valida metadata/JSON/gzip publicados y staging CAS simulado/idempotente, sin OCI. El bundle es separado; no es séptimo asset.
- Graphify: no configurado; no se inicializó.
- Sentrux: **DEGRADED, no aprobado** frente al baseline inicial; calidad 7780→6607, complejidad 0→104, coupling 0→0.07; cero ciclos/archivos dominantes. Sin reglas propias. Referencia congelada del producto: calidad 6589 y 89 funciones complejas; no sustituye el baseline.
- Codex: GPT-6.1 Sol High -- aceptación OCI y recuperación. [Referencia](https://learn.chatgpt.com/docs/model-selection)

Seis skips: GIS con opt-in, cuatro comprobaciones Spark/JDK/Delta y Nginx local. Nginx se comprobó aparte realmente en Linux en la extracción; no se declara aceptación de la VM nativa. Persisten avisos npm heredados (un crítico y siete altos), con revisión del consumidor/regresiones documentadas; no audit limpio ni actualización del pin para ocultarlos.

Dos suites/archivos del instalador combinado permanecen como evidencia tras rechazo de auto-review a su borrado. No se reintentó eliminarlos; están excluidos de la aplicación/imagen. `apps/backend/tests/validation-scope.json` mantiene clasificación y sustitutos. No se declara aprobada toda la suite histórica. Arko guía responsabilidades, sin declarar `arko check` aprobado para este layout.

La revisión independiente acotada detectó y cerró omisiones de referencia, pin TLS, salida pública, selección/paginación, permisos y Resume; sin hallazgos abiertos en ese alcance. No se midieron ahorro ni tokens. Windows requirió escalación/temporales nuevos por ACLs; no se borraron corridas previas. Un intento inicial sin escalación falló y no se contó como check aprobado. Diff y escáner de secretos se ejecutan en el cierre; no leen `.oci` ni imprimen valores.

## Entrega al coordinador

Orden autorizado: Governance→Market→GodEye sobre **un solo AIDP**. Usar fuente `ref=v1.0.2`, SHA indicado y `release_tag=v1.0.2`; `aidp_mode=existing`, `existing_ai_data_platform_ocid` y `existing_workspace_key` iguales a los outputs exactos de la primera instalación. Dominio ACTIVE y administrador ACTIVE con permisos efectivos verificados. Esos OCID/key reales aún no se conocen en este candidato; no se inventan.

El coordinador conserva Browser, Docker compartido, colas y mutaciones OCI. El registro original no acredita la aceptación del catálogo/handoff CTN en un entorno instalado; su estado operativo debe verificarse allí. [Contrato exacto de assets](../private-artifact-handoff.md), sin tokens GitHub en hooks/VM.

Pendientes: aceptación de IAM/roles, capacidad/arranque VM, confianza del certificado en Browser, instalación compartida/new-existing, recuperación, permisos negativos, task/publicación y conversación de la revisión instalada. Sin ampliar calidad de respuestas ni actores pagados. Sentrux y avisos heredados requieren revisión antes de producción.
