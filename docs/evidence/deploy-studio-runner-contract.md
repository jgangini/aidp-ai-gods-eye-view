# Compatibilidad del runner: preparación de v1.0.3

Fuente comprobada: `6cf5814ca8c5dc44ab0b2333473c4745e3871a49`. La [release v1.0.3](https://github.com/jgangini/aidp-ai-gods-eye-view/releases/tag/v1.0.3), ID `436133209`, está publicada e inmutable con seis assets verificados. La revisión automática rechazó inicialmente la publicación desde este chat; el coordinador la publicó después desde el chat con autorización directa del usuario. Esta evidencia conserva el alcance de la preparación original.

El [recibo publicado](../releases/v1.0.3.json) confirma el estado remoto y los mismos assets del [recibo histórico del borrador](../releases/v1.0.3-candidate.json). Las releases v1.0.0, v1.0.1 y v1.0.2 mantienen sus IDs, assets, tamaños, SHA-256 e inmutabilidad. El manifiesto de v1.0.3 utiliza schema 1; un motor Deploy Studio exclusivo de schema 2 requiere una release posterior compatible.

## Contratos corregidos

- CloudTechNext serializa `compartment` como string con `compartment_mode` en preflight y como objeto resuelto sin mode en post-apply. `first_install.compartment_scope` utiliza la tenancy para consultas previas a un compartimento nuevo, el OCID seleccionado para uno existente y exige coincidencia con Terraform en post-apply. Las entradas malformadas fallan antes de consultar Compute; no amplían permisos.
- El consumidor `declared_state_outputs` filtra el state mediante `manifest.outputs`. El manifiesto declara los 15 outputs Terraform no sensibles consumidos y los seis derivados del hook. Las regresiones proyectan el state antes de resolver ambos modos de workspace, crear el entorno de VM y construir el runtime nativo.
- Preflight exige una clave exacta para un `oci_medallion` externo, comprueba tipo `INTERNAL` e identidad y bloquea una coincidencia solo por nombre antes de APPLY. Resume puede leer su recibo verificado sin escribir ni adquirir lease. Post-apply reutiliza la identidad compartida y su journal CAS, con la clave ya registrada.

Se contrastaron los serializadores, parser y proyección reales del checkout CloudTechNext. Sus servicios, catálogo de proyectos y runtime no se modificaron. Dos agentes acotados aportaron la regresión del filtro y la revisión estática de identidad/Resume; la revisión no encontró hallazgos accionables. Los checks comunes se ejecutaron una sola vez desde el dueño del repositorio; no hay medición de ahorro de tiempo o tokens.

## Validación realizada

- Preflight: `scripts/arch-preflight.ps1`, gate DEGRADED con baseline inicial conservado.
- Postflight: `scripts/arch-postflight.ps1`, **1699 passed, 6 skipped**; tres programas y tres manifiestos AIDP verificados, formato/validate Terraform y tres mocks aprobados. El comando global falla por Sentrux.
- [CI 42168548647](https://github.com/jgangini/aidp-ai-gods-eye-view/actions/runs/42168548647): seis jobs aprobados. Python: 1699 passed, 6 skipped; controles React: 89 tests/build; visor nativo: 119 tests/build; rollback simulado y tres imágenes empaquetadas.
- Localmente se omitieron GIS opt-in, cuatro escenarios Spark/JDK/Delta y Nginx ausente. En CI Nginx sí se comprobó; el sexto skip fue el consumidor CTN externo, comprobado localmente. No sumar los resultados como pruebas distintas.
- Parser/extractor CTN real: ZIP de **46.631.066 bytes**, selección de **88 archivos / 1.157.046 bytes**, dentro de 100 MiB / 250 archivos / 10 MiB. No se modificaron límites ni se eludió el catálogo confiable para acreditar una instalación.
- Bundle CI: **22.709 bytes**, SHA-256 `7fab22b0c20c405f79718b58b77071f64c99dd4d3c0c61ea0c7bc57bf44a4a7b`. Revisión del host Linux V2: `77909c23cfa39ac899a9c04e817cd2290fee4ccdbc16f6bea2acf708c37737d5`, igual a v1.0.2. La reproducción local fijó metadata ZIP Linux; el artifact CI confirmó los bytes efectivos.
- Handoff real de los seis archivos del borrador: preflight con JSON, post-apply con todos los bytes y CAS simulado aprobados; tres cargas iniciales, ninguna al repetir. Sin OCI.
- Sentrux: calidad 6607 → 6610 en este ajuste; frente al baseline inicial 7780 sigue DEGRADED, coupling 0,07 y 104 funciones complejas; cero ciclos/god files. Sin reglas personalizadas. Graphify no configurado; no se inicializó.

## Revisión estática de publicación

Se verificaron los seis tamaños/SHA-256 remotos y los manifiestos por componente, commit, tag propuesto, plataforma e ID. Los gzip son los bytes de CI; solo los JSON se promovieron de `candidate` a `v1.0.3`.

Se examinaron sin ejecutar contenedores las tres imágenes, incluidas sus capas históricas: **34 capas únicas, 80.909 archivos y 1.565.684.520 bytes de contenido**. Se revisaron tres configuraciones de imagen. Las coincidencias de firmas/contexto en 68 archivos ya revisados conservaron sus hashes. Las seis coincidencias nuevas corresponden a bytecode de ejemplos de URL de httpx, urllib3 y Pydantic: su payload compilado es byteidéntico al revisado en v1.0.2; solo difiere el encabezado `.pyc` de 16 bytes. No se ejecutó ese bytecode ni se imprimieron valores candidatos.

El escáner del repositorio y `git diff --check` se ejecutaron antes de subir la fuente. La revisión por patrones no acredita ausencia absoluta de secretos ni resuelve los [avisos heredados de dependencias](native-dependency-review.md).

La publicación de v1.0.3 está confirmada; registro del catálogo y aceptación de IAM/roles, capacidad VM, confianza TLS en Browser, workflows/publicaciones AIDP y conversación del agente corresponden al coordinador. Este trabajo no ejecutó OCI, inferencia ni actores pagados.
