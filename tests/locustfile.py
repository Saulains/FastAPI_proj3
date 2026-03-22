import uuid

from locust import HttpUser, between, task


class ShortLinkUser(HttpUser):
    wait_time = between(0.1, 0.5)

    def on_start(self):
        self.short_code = None

    @task(3)
    def create_short_link(self):
        response = self.client.post(
            "/links/shorten",
            json={"original_url": f"https://example.com/{uuid.uuid4()}"},
            name="POST /links/shorten",
        )
        if response.status_code == 201:
            self.short_code = response.json().get("short_code")

    @task(1)
    def get_link_stats(self):
        if self.short_code:
            self.client.get(
                f"/links/{self.short_code}/stats",
                name="GET /links/.../stats",
            )