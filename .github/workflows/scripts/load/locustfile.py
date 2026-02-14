from locust import HttpUser, between, task


class ApiUser(HttpUser):
    wait_time = between(1, 2)

    def on_start(self):
        res = self.client.post('/auth/login', json={'user_id': 'load_user'})
        token = res.json()['access_token']
        self.headers = {'Authorization': f'Bearer {token}'}

    @task(3)
    def chat_analyze(self):
        self.client.post('/chat/analyze', headers=self.headers, json={'text': 'maybe later', 'tone_preference': 'business'})

    @task(2)
    def onboarding_plan(self):
        self.client.post('/onboarding/calculate-plan', headers=self.headers, json={'goal_type': 'business', 'target_language': 'English', 'minutes_per_day': 10})

    @task(1)
    def import_and_check(self):
        create = self.client.post('/import', headers=self.headers, json={'channel': 'daily', 'content': 'hello'})
        if create.status_code == 200:
            job_id = create.json()['job_id']
            self.client.get(f'/import/{job_id}', headers=self.headers)
