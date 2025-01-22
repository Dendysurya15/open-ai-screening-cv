from openai import OpenAI
import base64
import requests

# Point to the local server
client = OpenAI(base_url="http://10.9.116.113:1234/v1", api_key="lm-studio")

# Ask the user for a path on the filesystem:
path = input("Enter a local filepath to an image: ")

# Read the image and encode it to base64:
base64_image = ""
try:
    with open(path.replace("'", ""), "rb") as image_file:
        image = image_file.read()
        base64_image = base64.b64encode(image).decode("utf-8")
    print("Image successfully encoded to base64.")
except Exception as e:
    print(f"Couldn't read the image. Error: {e}")
    exit()

# Prepare the message payload
messages = [
    {
        "role": "system",
        "content": "This is a chat between a user and an assistant. The assistant is helping the user to describe an image.",
    },
    {
        "role": "user",
        "content": [
            {"type": "text", "text": "What’s in this image?"},
            {
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/jpeg;base64,{base64_image}"
                },
            },
        ],
    }
]

# Make the API call
try:
    print("Making the API call...")
    completion = client.chat.completions.create(
        model="QuantFactory/Meta-Llama-3-8B-Instruct-GGUF",
        messages=messages,
        max_tokens=1000,
        stream=True
    )

    # Check if completion is not None
    if completion is None:
        print("The API returned an empty response.")
    else:
        print("Processing the API response...")
        # Print the raw completion response
        print("Raw API response:", completion)

        # Process the streamed response
        for chunk in completion:
            if chunk and chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
                print(chunk.choices[0].delta.content, end="", flush=True)
            else:
                print("No content in this chunk:", chunk)

except Exception as e:
    print(f"An error occurred: {e}")
