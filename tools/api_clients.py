import requests
import time

class APIClient:
    def __init__(self, base_url=None, timeout=5):
        self.base_url = base_url
        self.timeout = timeout

    def get(self, endpoint, retries=2):
        url = f"{self.base_url}/{endpoint}"
        
        for attempt in range(retries + 1):
            try:
                response = requests.get(url, timeout=self.timeout)

                if response.status_code == 200:
                    return {"status": "success", "data": response.json()}
                else:
                    return {
                        "status": "fail",
                        "code": response.status_code,
                        "message": response.text
                    }

            except Exception as e:
                if attempt < retries:
                    time.sleep(1)  # retry delay
                else:
                    return {"status": "error", "message": str(e)}

    def post(self, endpoint, payload, retries=2):
        url = f"{self.base_url}/{endpoint}"

        for attempt in range(retries + 1):
            try:
                response = requests.post(url, json=payload, timeout=self.timeout)

                if response.status_code in [200, 201]:
                    return {"status": "success", "data": response.json()}
                else:
                    return {
                        "status": "fail",
                        "code": response.status_code,
                        "message": response.text
                    }

            except Exception as e:
                if attempt < retries:
                    time.sleep(1)
                else:
                    return {"status": "error", "message": str(e)}

    def health_check(self):
        try:
            response = requests.get(self.base_url, timeout=self.timeout)
            return {
                "status": "healthy" if response.status_code == 200 else "unhealthy",
                "code": response.status_code
            }
        except:
            return {"status": "down"}