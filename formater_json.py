import json
import glob
import os

def format_json_file(input_path, output_path=None):
    # Read the JSON file
    with open(input_path, 'r', encoding='utf-8') as file:
        data = json.load(file)
    
    # Custom formatting function
    def custom_format(obj, indent=0):
        if isinstance(obj, dict):
            result = "{\n"
            for i, (key, value) in enumerate(obj.items()):
                result += " " * (indent + 2) + f'"{key}": '
                result += custom_format(value, indent + 2)
                if i < len(obj) - 1:
                    result += ","
                result += "\n"
            result += " " * indent + "}"
            return result
        elif isinstance(obj, list):
            if not obj:
                return "[]"
            result = "[\n"
            for i, item in enumerate(obj):
                result += " " * (indent + 2) + custom_format(item, indent + 2)
                if i < len(obj) - 1:
                    result += ","
                result += "\n"
            result += " " * indent + "]"
            return result
        elif isinstance(obj, str):
            return f'"{obj}"'
        else:
            return json.dumps(obj)

    # Format the JSON with custom formatting
    formatted_json = custom_format(data)
    
    # Write to output file
    if output_path is None:
        filename, ext = os.path.splitext(input_path)
        output_path = f"{filename}_formatted{ext}"
    
    with open(output_path, 'w', encoding='utf-8') as file:
        file.write(formatted_json)
    
    return output_path

def format_all_json_files(directory_path, output_directory=None):
    # Create output directory if it doesn't exist
    if output_directory and not os.path.exists(output_directory):
        os.makedirs(output_directory)
    
    # Get all JSON files in the directory
    json_files = glob.glob(os.path.join(directory_path, "*.json"))
    
    formatted_files = []
    for json_file in json_files:
        if output_directory:
            filename = os.path.basename(json_file)
            output_path = os.path.join(output_directory, filename)
        else:
            output_path = None
            
        formatted_path = format_json_file(json_file, output_path)
        formatted_files.append(formatted_path)
    
    return formatted_files

# Example usage:
if __name__ == "__main__":
    # Format a single file
    input_file = "prompts/prompt_11_20250116_091021.json"
    formatted_file = format_json_file(input_file)
    print(f"Formatted file saved to: {formatted_file}")
    
    # Or format all JSON files in a directory
    # directory = "prompts/"
    # output_dir = "formatted_prompts/"
    # formatted_files = format_all_json_files(directory, output_dir)
    # print("Formatted files:", formatted_files)