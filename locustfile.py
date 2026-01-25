from locust import HttpUser, task, between

class AgenciaUser(HttpUser):
    # Simula que el usuario espera entre 1 y 3 segundos entre cada acción
    wait_time = between(1, 3)

    @task(5)
    def navegar_home(self):
        """Entra en la página principal (la tarea más común)"""
        self.client.get("/")

    @task(2)
    def ver_admin_con_busqueda(self):
        """Simula al administrador buscando por DNI (tarea pesada de DB)"""
        # Cambia el DNI por uno que exista en tu base de datos para probar el AES_DECRYPT
        self.client.get("/admin?q=76653343E", auth=("admin", "cosmin"))

    @task(1)
    def simular_error(self):
        """Entra en una ruta que no existe para ver cómo responde el servidor"""
        self.client.get("/ruta-inexistente")