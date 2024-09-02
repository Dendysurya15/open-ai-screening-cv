import os
import openai

# Point to the local server
client = openai.OpenAI(base_url="http://localhost:1234/v1", api_key="lm-studio")

# Initialize chat history
history = [
    {"role": "system", "content": "You are an intelligent assistant. You always provide well-reasoned answers that are both correct and helpful."},
    {"role": "user", "content": "Hello, introduce yourself to someone opening this program for the first time. Be concise."},
]

def print_response(response):
    print(response["content"], end="", flush=True)

def read_file(file_path):
    with open(file_path, "r") as file:
        content = file.read()
    return content

while True:
    # Display options
    print("\nOptions:")
    print("1: Chat")
    print("2: Read a file")
    print("3: Exit")

    choice = input("> Choose an option: ")

    if choice == "1":
        user_input = input("> You: ")
        history.append({"role": "user", "content": user_input})

        completion = client.Completion.create(
            model="lmstudio-community/gemma-2-2b-it-GGUF/gemma-2-2b-it-Q4_K_M.gguf:2",
            messages=history,
            temperature=0.7,
            stream=True,
        )

        new_message = {"role": "assistant", "content": ""}

        for chunk in completion:
            if chunk.choices[0].delta.content:
                print(chunk.choices[0].delta.content, end="", flush=True)
                new_message["content"] += chunk.choices[0].delta.content

        history.append(new_message)
        print()

    elif choice == "2":
        file_path = input("> Enter the file path to read: ")
        if os.path.exists(file_path):
            content = read_file(file_path)
            print("\nFile Content:\n")
            print(content)
        else:
            print("File not found. Please check the path and try again.")

    elif choice == "3":
        print("Exiting...")
        break

    else:
        print("Invalid option. Please try again.")
