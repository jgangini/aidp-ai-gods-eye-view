# Operación del candidato

El coordinador posee instalación nativa, catálogo Deploy Studio y transición de entornos. Este candidato no autoriza adoptar ni modificar la VM del stack original. La separación de repositorios no transfiere Terraform state ni concede permisos nuevos.

La VM ejecuta gateway, API y visor mediante Compose. Solo se publica TLS 443. El administrador seleccionado en Deploy Studio es una identidad administrativa de la aplicación/AIDP; las peticiones OCI siguen firmadas por el operador autorizado. La administración de streaming/proveedores se abre dentro del visor; Deploy y Redeploy no aparecen en esa interfaz.

`docker/bootstrap.sh start` exige digests de las tres imágenes y configuración preparada. Excluye activaciones concurrentes y guarda un recibo que vincula imágenes y `runtime.env`. Si falla la activación, restaura ambos del recibo anterior y conserva el puntero vigente. Datos, controles, checkpoints y caché no se borran. Hay prueba reproducible de fallo/rollback con comandos Docker simulados; no equivale a ensayo de actualización nativa.

Ese rollback no revierte esquema Gold, IAM, claves OCI ni certificados TLS. La primera extracción conserva formatos y operador; rotaciones o cambios incompatibles requieren otra operación explícita, con snapshot y recuperación revisados. No reutilizar una imagen anterior con un esquema o identidad incompatibles.

Un error o timeout conserva el recibo y recursos. Resume revalida el mismo administrador y destino; rechaza otro binding. Un catálogo creado cuyo API no devolvió identidad exige reconciliar el request antes de Resume, sin buscar/adoptar por nombre. Los límites de recuperación de operaciones nativas asíncronas y del arranque inicial deben aceptarse en OCI antes de publicar una release.

La calidad del agente requiere conversaciones de la revisión instalada y evidencia Gold de esa publicación. Run/Pause de captura no detiene compute; no borrar checkpoints ni reiniciar writers para esconder un error. Los costes y capacidad de compute no fueron medidos durante la extracción.

Las dependencias upstream permanecen fijadas. El diagnóstico encontró avisos npm heredados: DOMPurify crítico requiere un modo de uso distinto del consumidor Cesium identificado; una regresión comprueba ese consumidor. Siete avisos altos se relacionan con QA/build o rutas de desarrollo Vite no observadas en preview Linux. No se confirmó exposición productiva en esta revisión; los paquetes siguen presentes y deben revisarse si cambia su uso. La guía del visor conserva el detalle y las fuentes.
