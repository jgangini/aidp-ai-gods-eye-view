# Formulario completo de Deploy Studio: candidato v2.0.0

El [PR #1](https://github.com/jgangini/aidp-ai-gods-eye-view/pull/1) incorpora `schema_version: 2` y `form.groups` sobre `f74fb0b2f8fa675b186f03e9e1839970d2937b62`. El cambio semántico del manifiesto se limita a esas dos propiedades. Hooks, recursos Terraform, runtime, API y visor conservan sus fuentes de v1.0.3. El contrato de operación permanece en [Instalación e identidad](../contracts.md).

La candidata usa `v2.0.0` por el cambio incompatible del contrato de formulario. Requiere el motor Deploy Studio exclusivo de schema 2. La publicación del motor y la aceptación OCI corresponden al coordinador.

## Formulario y regresiones

- El primer grupo `credentials` contiene exclusivamente `oci_config` y `oci_key`.
- `services` declara región, modo, nombre nuevo y compartimento existente en ese orden. Región tiene `span: 2`, una fila completa encima de los controles de compartimento.
- Los 15 campos de aplicación aparecen exactamente una vez; las opciones del control de modo coinciden con `capabilities.compartment_modes`. No se declaran campos password ni generadores.
- La regresión portable comprueba el manifiesto completo y la disposición aceptada. El consumidor CTN real comprueba el parser/proyección cuando su checkout está disponible y rechaza manifiestos schema 1 y schema 2 sin grupos. No se añadió código de compatibilidad.
- Los contextos de hooks y los manifiestos de imágenes conservan sus propios protocolos; la versión 2 corresponde al manifiesto de formulario.

## Validación ejecutada

- Preflight: `scripts/arch-preflight.ps1`, fallo histórico Sentrux con baseline inicial preservado.
- Foco: nueve regresiones aprobadas. Tras el ajuste Thermos de `span: 2`, el postflight final volvió a cubrir la regresión actualizada.
- Postflight final: `scripts/arch-postflight.ps1`; **1700 passed, 6 skipped**, tres programas y tres manifiestos AIDP válidos, formato/validate Terraform y tres mocks aprobados. El comando completo termina con error por Sentrux.
- [CI del commit](https://github.com/jgangini/aidp-ai-gods-eye-view/actions/runs/42224278241): seis jobs aprobados, Python 1700 passed / seis skips, 89 tests/build de controles, 119 tests/build del visor, rollback simulado y tres imágenes empaquetadas. Los checks del PR también aprobaron. No sumar ejecuciones como cobertura distinta.
- Skips locales: GIS opt-in, cuatro escenarios Spark/JDK/Delta y Nginx ausente. En CI Nginx sí pasó y el sexto skip fue el consumidor CTN externo, comprobado localmente.
- Parser/extractor CTN real sobre ZIP del commit: **46.637.976 bytes**, **88 archivos / 1.160.361 bytes** seleccionados; límites conservados de 100 MiB / 250 archivos / 10 MiB.
- Bundle CI: 22.709 bytes, SHA-256 `7fab22b0c20c405f79718b58b77071f64c99dd4d3c0c61ea0c7bc57bf44a4a7b`; revisión del host Linux V2 `77909c23cfa39ac899a9c04e817cd2290fee4ccdbc16f6bea2acf708c37737d5`, iguales a v1.0.3.
- Sentrux antes/después: calidad 6610, coupling 0,07, 104 funciones complejas, cero ciclos/god files. El gate sigue DEGRADED frente al baseline inicial 7780. Sin reglas personalizadas.
- Graphify: reporte/wiki existentes consultados y una consulta del grafo ejecutada. Sus archivos y actualización permanecen bajo responsabilidad del coordinador; este trabajo no los modificó ni incluyó en su commit. El postflight no alcanza su paso Graphify porque falla antes en Sentrux.

## Assets y publicación

El borrador ID `436528205` conserva exactamente seis assets: tres gzip de CI sin cambios y tres JSON promovidos a `v2.0.0`. Se verificaron ID, tamaño y SHA-256 remotos, plataforma, tag y SHA de fuente de cada manifiesto. El [recibo del candidato](../releases/v2.0.0-candidate.json) registra esos valores.

El handoff local pasó con JSON en preflight y los seis archivos en post-apply. CAS simulado realizó tres cargas iniciales y ninguna al repetir. No se llamó a OCI.

La revisión estática cubrió tres imágenes, 34 capas únicas, 80.909 archivos y 1.565.684.520 bytes, incluidas capas anteriores, sin ejecutar contenedores. Los 68 archivos con coincidencias ya revisadas conservaron sus hashes. Se cerraron seis coincidencias nuevas de bytecode: su payload compilado coincide con el revisado en v1.0.2 y solo difiere el encabezado `.pyc` de 16 bytes. No se ejecutó el bytecode ni se imprimieron valores candidatos. Los avisos heredados de dependencias siguen en su [evidencia propia](native-dependency-review.md).

**La candidata no está publicada ni es inmutable todavía.** La revisión automática rechazó la conversión del borrador porque la autorización de migración no acredita, para ese control, aprobación de esta nueva release pública e inmutable y sus seis assets. No se reintentó ni se usó otra vía. La publicación queda en el gate del coordinador; no se solicitó otra aprobación al usuario desde este chat.

Las releases previas se conservan. El [recibo publicado de v1.0.3](../releases/v1.0.3.json) reconcilia su publicación posterior por el coordinador con los hashes del borrador original. Este trabajo no ejecutó OCI, Apify, Docker compartido ni Browser. El formulario real y los despliegues esperan el motor CTN correspondiente.
