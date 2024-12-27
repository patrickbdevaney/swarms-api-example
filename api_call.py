import os
import requests
import json
from datetime import datetime
import random
import time
from typing import Any, Dict
from dotenv import load_dotenv

# Load environment variables from the .env file
load_dotenv()

class SwarmsAPIClient:
    def __init__(self, base_url: str = "https://api.swarms.ai/v1", debug: bool = True):
        self.base_url = base_url
        self.api_key = os.getenv('OPENAI_API_KEY')
        self.openai_api_key = os.getenv('OPENAI_API_KEY')  # Load OpenAI API key
        self.user_id = None
        self.debug = debug

        if not self.api_key:
            raise ValueError("OPENAI_API_KEY environment variable is not set.")
        if not self.openai_api_key:
            raise ValueError("OPENAI_API_KEY environment variable is not set.")

    def _debug_print(self, message: str, data: Any = None):
        if self.debug:
            print(f"\nDEBUG: {message}")
            if data is not None:
                print(json.dumps(data, indent=2) if isinstance(data, (dict, list)) else str(data))

    def _handle_response(self, response: requests.Response, operation: str) -> Dict[str, Any]:
        self._debug_print(f"Response Status Code: {response.status_code}")
        self._debug_print("Response Headers:", dict(response.headers))
        self._debug_print("Raw Response Text:", response.text)

        try:
            if response.status_code == 204:
                return {}

            if not response.content:
                raise Exception(f"Empty response received from {operation}")

            result = response.json()
            self._debug_print("Parsed JSON Response:", result)
            return result
        except json.JSONDecodeError as e:
            raise Exception(f"Invalid JSON response from {operation}: {str(e)}\nRaw response: {response.text}")
        except requests.exceptions.RequestException as e:
            raise Exception(f"Request failed during {operation}: {str(e)}")

    def create_user(self, username: str) -> Dict[str, Any]:
        endpoint = f"{self.base_url}/users"
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

        body = {"username": username}

        self._debug_print("Creating user with endpoint:", endpoint)
        self._debug_print("Request Headers:", headers)
        self._debug_print("Request Body:", body)

        try:
            response = requests.post(endpoint, headers=headers, json=body)
            result = self._handle_response(response, "User creation")

            self.api_key = result.get('api_key')
            self.user_id = result.get('user_id')

            return result
        except Exception as e:
            self._debug_print("Error in create_user:", str(e))
            raise Exception(f"Failed to create user: {str(e)}")

    def create_api_key(self, user_id: str) -> Dict[str, Any]:
        endpoint = f"{self.base_url}/users/{user_id}/api-keys"
        headers = {
            "api-key": self.api_key,
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

        body = {"name": "new_api_key"}

        self._debug_print("Creating API key with endpoint:", endpoint)
        self._debug_print("Request Headers:", headers)
        self._debug_print("Request Body:", body)

        try:
            response = requests.post(endpoint, headers=headers, json=body)
            result = self._handle_response(response, "API key creation")
            return result
        except Exception as e:
            self._debug_print("Error in create_api_key:", str(e))
            raise Exception(f"Failed to create API key: {str(e)}")

    def create_agent(self,
                      agent_name: str,
                      system_prompt: str = "You are a helpful AI assistant.",
                      model_name: str = "gpt-4",
                      temperature: float = 0.7) -> Dict[str, Any]:
        max_attempts = 3
        for attempt in range(max_attempts):
            if not self.api_key:
                raise Exception("No API key available. Create a user first.")

            endpoint = f"{self.base_url}/agent"
            headers = {
                "api-key": self.api_key.strip(),
                "Content-Type": "application/json",
                "Accept": "application/json"
            }

            agent_config = {
                "agent_name": agent_name,
                "model_name": model_name,
                "description": "API-created agent",
                "system_prompt": system_prompt,
                "temperature": temperature,
                "max_loops": 1,
                "autosave": True,
                "dashboard": False,
                "verbose": True,
                "dynamic_temperature_enabled": True,
                "user_name": "default_user",
                "retry_attempts": 1,
                "context_length": 200000,
                "output_type": "string",
                "streaming_on": False,
                "tags": ["api_created"]
            }

            self._debug_print("Creating agent with endpoint:", endpoint)
            self._debug_print("Request Headers:", headers)
            self._debug_print("Request Body:", agent_config)

            try:
                response = requests.post(endpoint, headers=headers, json=agent_config)
                result = self._handle_response(response, "Agent creation")
                if 'agent_id' not in result:
                    if response.status_code == 401:
                        if attempt < max_attempts - 1:
                            print("API Key is invalid or expired. Creating a new user...")
                            # Generate a new username for the new user
                            new_username = f"user_{random.randint(1000, 9999)}"
                            self.create_user(new_username)
                            continue  # Retry with new API key
                        else:
                            raise Exception("API Key remains invalid after multiple attempts.")
                    else:
                        raise Exception("Agent creation failed; no agent_id in response.")
                return result
            except Exception as e:
                self._debug_print(f"Error in create_agent, attempt {attempt + 1}:", str(e))
                if attempt == max_attempts - 1:  # If it's the last attempt, raise the error
                    raise

    def generate_completion(self, api_key: str, agent_id: str, prompt: str, max_retries: int = 3) -> Dict[str, Any]:
        if not self.api_key:
            raise Exception("No API key available. Ensure a user is created.")

        endpoint = f"{self.base_url}/agent/completions"
        headers = {
            "api-key": api_key.strip(),
            "Content-Type": "application/json",
            "Accept": "application/json",
            "OpenAI-API-Key": self.openai_api_key  # Include OpenAI API key
        }
        body = {
            "prompt": prompt,
            "agent_id": agent_id
        }

        self._debug_print("Generating completion with endpoint:", endpoint)
        self._debug_print("Request Headers:", headers)
        self._debug_print("Request Body:", body)

        for attempt in range(max_retries):
            try:
                response = requests.post(endpoint, headers=headers, json=body)
                result = self._handle_response(response, "Completion generation")

                # Check if the agent wasn't found
                if result.get('detail', '').startswith('Error processing completion: 404'):
                    if attempt < max_retries - 1:  # Don't print this on the last attempt
                        print(f"Agent not found. Retrying in {5} seconds...")
                        time.sleep(5)  # Fixed delay
                    else:
                        raise Exception(f"Agent {agent_id} still not found after retries.")
                else:
                    return result
            except Exception as e:
                if attempt == max_retries - 1:  # If this was the last attempt
                    raise
                print(f"Attempt {attempt + 1} failed. Retrying in {5} seconds...")
                time.sleep(5)  # Fixed delay

def main():
    client = SwarmsAPIClient(debug=True)

    try:
        print("\n=== Starting API Interaction ===")

        # Step 1: Create User
        random_number = random.randint(1000, 9999)
        username = f"swarms_user_{random_number}"
        print(f"\nStep 1: Creating user with username: {username}")
        user_result = client.create_user(username)

        # Store results in JSON format
        result_json = {
            "user": {
                "username": username,
                "api_key": client.api_key,
                "user_id": client.user_id
            }
        }

        # Step 2: Create API Key
        print("\nStep 2: Creating API key...")
        api_key_result = client.create_api_key(client.user_id)
        print(f"API Key: {api_key_result}")

        # Update the client's API key to the newly created one
        client.api_key = api_key_result.get('key')

        # Step 3: Create Agent
        print("\nStep 3: Creating agent...")
        agent_result = client.create_agent(
            agent_name=f"Agent_{username}",
            system_prompt="You are an AI specialized in answering questions about geography.",
            temperature=0.7
        )

        if 'agent_id' in agent_result:
            agent_id = agent_result['agent_id']
            result_json["agent"] = {
                "agent_id": agent_id,
                "agent_name": f"Agent_{username}"
            }

            # Generate completion
            print("\nStep 4: Generating completion...")
            completion_prompt = "What is the capital of France?"

            try:
                completion = client.generate_completion(client.api_key, agent_id, completion_prompt)

                # Handle the case where the response is "None"
                if completion.get("response") == "None":
                    print("Warning: The API returned 'None' as the response.")
                    result_json["completion"] = {
                        "prompt": completion_prompt,
                        "response": "API returned no response",
                        "metadata": completion.get("metadata", {}),
                        "timestamp": completion.get("timestamp"),
                        "processing_time": completion.get("processing_time"),
                        "token_usage": completion.get("token_usage", {})
                    }
                else:
                    result_json["completion"] = {
                        "prompt": completion_prompt,
                        "response": completion.get("response", "No response"),
                        "metadata": completion.get("metadata", {}),
                        "timestamp": completion.get("timestamp"),
                        "processing_time": completion.get("processing_time"),
                        "token_usage": completion.get("token_usage", {})
                    }
            except Exception as e:
                print(f"Failed to generate completion: {str(e)}")
                result_json["completion"] = {
                    "prompt": completion_prompt,
                    "response": f"Error: {str(e)}"
                }

            # Write to JSON file
            with open('swarms_api_results.json', 'w') as f:
                json.dump(result_json, f, indent=2)

            print(f"\nAll results saved to 'swarms_api_results.json'")

    except Exception as e:
        print(f"\nError occurred: {str(e)}")

if __name__ == "__main__":
    main()
