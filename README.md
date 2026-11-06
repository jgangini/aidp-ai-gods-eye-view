# God’s Eye View para Oracle AIDP

God’s Eye View reúne reportes sociales, sensores, evidencia y revisión humana en un mapa compartido. Consulta publicaciones Gold mediante AIDP y ofrece un agente LangGraph con referencias a esa evidencia. La configuración de fuentes, horarios, streaming y proveedores se abre dentro del propio visor.

La instalación y las actualizaciones se realizan desde Deploy Studio. La aplicación tiene API, identidad y controles propios; no necesita el portal Starter Kits. Los lectores consultan el visor y el agente, mientras que la administración exige una identidad autorizada y permisos efectivos comprobados en servidor.

## Componentes

| Componente | Responsabilidad |
| --- | --- |
| Visor nativo | Globo, Data Layers, escenas, evidencia, sensores, Agent Flow y voz; fuente upstream fijada en [`upstream.json`](modules/ai-gods-eye-view/upstream.json). |
| Controles integrados | Formularios React en `/controls/` para fuentes, horarios, proveedores e identidad del visor, accesibles desde **Source controls**. |
| API del producto | FastAPI con sesiones OIDC, autorización, captura, controles durables y consulta de publicaciones AIDP. |
| Programas AIDP | Streams social/sensor y agente organizados por capas en `/Workspace/medallion/gods_eye_view/`; fuentes y ensamblado en [`aidp/manifest.json`](aidp/manifest.json). |
| Infraestructura | Una VM con gateway TLS, API y visor en tres contenedores Compose; Terraform y hooks invocados por Deploy Studio. |

Solo el gateway publica HTTPS 443. API, bridge y Node permanecen en la red interna. Las consultas analíticas usan Gold de AIDP; controles y diarios usan Object Storage. Los lectores y escritores de estos flujos no requieren Autonomous. La procedencia real o sintética de los datos permanece visible; un marcador o una respuesta del modelo no acredita por sí solo una emergencia real.

## Requisitos

- Deploy Studio con el proyecto `aidp-ai-gods-eye-view` habilitado y soporte del selector `oci_identity_domains`, del selector de administradores AIDP y del [handoff de assets](docs/private-artifact-handoff.md).
- Una cuenta operadora OCI autorizada para los recursos elegidos, un Identity Domain activo y un administrador activo de ese dominio. El operador que firma peticiones OCI y el administrador seleccionado conservan identidades y responsabilidades distintas.
- Una región suscrita con AIDP y modelos conversacionales OCI disponibles, cuotas y capacidad para la VM y los computes del producto. El shape predeterminado es `VM.Standard.E5.Flex`, con 2 OCPU y 16 GiB; son valores de configuración, no un dimensionamiento medido para cada carga.
- Cinco buckets distintos: Landing, Bronze, Silver, Gold y artifacts. Al reutilizar plataforma, workspace o catálogo, disponer de sus identificadores exactos y permisos correspondientes.
- Una release estable e inmutable de este [repositorio público](https://github.com/jgangini/aidp-ai-gods-eye-view), con los seis assets de imagen vinculados a su commit. Los artifacts CI etiquetados `candidate` no son releases instalables.

La VM necesita salida a OCI y repositorios de paquetes. No se pide al usuario un dominio, certificado, clave TLS, imagen Oracle Linux, availability domain ni objeto/hash del bundle de arranque: el preflight y Terraform derivan esos valores. El certificado público generado para la IP requiere confianza explícita del navegador antes de iniciar OIDC.

## Instalación desde Deploy Studio

1. Abrir el proyecto **God’s Eye View** y seleccionar la release estable. El hook deriva el tag operativo de esa referencia y comprueba el commit; no se introduce otro tag en el formulario.
2. Seleccionar **Identity Domain** en el listado OCI y el administrador AIDP. El preflight comprueba dominio, cuenta y permisos aplicables; no es necesario escribir el OCID del dominio.
3. Elegir el destino AIDP:
   - **Create new platform** crea la plataforma y utiliza su workspace predeterminado. El post-apply asigna y vuelve a comprobar el rol administrativo del usuario seleccionado.
   - **Use existing platform** requiere `existing_ai_data_platform_ocid` y `existing_workspace_key` exactos. Si se reutiliza el catálogo `oci_medallion`, indicar su `existing_catalog_key`; un nombre coincidente no permite adoptarlo automáticamente.
4. En modo new, elegir **New AIDP name** (default `aidp_gods_eye_view`). Seleccionar el modelo en **Agent Flow**, el modo de buckets en **Artifacts** y los cinco nombres de buckets. El combobox `create_buckets=false` reutiliza los buckets existentes. El prefijo de infraestructura es interno y se conserva al reanudar. Conservar región, namespace e identidades de recursos compartidos.
5. Revisar recursos, permisos y costes en Deploy Studio e iniciar la instalación. El preflight fija una imagen pública Oracle Linux 9 y un AD compatibles; Terraform deriva el origen HTTPS de la IP asignada y registra ese mismo callback OIDC.
6. Obtener `application_url`, `viewer_certificate_pem` y `viewer_certificate_sha256` de los resultados autenticados de Deploy Studio. Verificar la huella y establecer confianza en esa hoja/IP según la política del navegador o equipo antes de abrir **Sign in with OCI**.

El estado `installed_conversation_pending` separa las comprobaciones de tareas/publicación y salud del visor de la aceptación de una conversación del agente. Verificar permisos de lector/administrador, revocación y concordancia con la publicación Gold en el entorno instalado. Las pruebas locales, un contenedor saludable o una release publicada no sustituyen esa aceptación OCI.

## Uso y operación

Los lectores acceden por `/gods-eye-view/`. El administrador utiliza **Source controls** para redes sociales, sensores, horarios y parámetros. La captura real de X exige credenciales y cuota; las otras redes y los sensores usan los modos sintéticos admitidos. Mantener identificada esa procedencia al revisar evidencia.

**Run** y **Pause** controlan la captura; pausar no detiene el compute. Reanudar una instalación o actualizar imágenes corresponde a Deploy Studio. Los recibos, controles CAS, checkpoints y datos compartidos deben conservarse ante errores y reintentos.

## Guías y contratos

- [Guía del visor, proveedores, voz y atribución](modules/ai-gods-eye-view/README.md)
- [Operación, recuperación, TLS y actualizaciones](docs/operations.md)
- [Desarrollo y validación](docs/development.md)
- [Contratos del producto e identidad](docs/contracts.md)
- [Contrato de releases y empaquetado](docs/release-contract.md)
- [Contrato de entrega de assets a los hooks](docs/private-artifact-handoff.md)
