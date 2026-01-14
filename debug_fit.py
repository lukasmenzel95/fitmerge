import fitdecode
import os

INPUT_FOLDER = 'input_files'
#!/usr/bin/env python3
def inspect_first_file():
    # Find the first .fit file
    if not os.path.exists(INPUT_FOLDER):
        print(f"Folder {INPUT_FOLDER} does not exist.")
        return

    files = [f for f in os.listdir(INPUT_FOLDER) if f.lower().endswith('.fit')]
    if not files:
        print("No .fit files found.")
        return

    target_file = os.path.join(INPUT_FOLDER, files[0])
    print(f"--- INSPECTING: {files[0]} ---")

    try:
        with fitdecode.FitReader(target_file) as fit:
            count = 0
            for frame in fit:
                # Look for data records
                if frame.frame_type == fitdecode.FIT_FRAME_DATA and frame.name == 'record':
                    print(f"\n[Record #{count}]")
                    
                    # Print ALL fields found in this record
                    found_fields = []
                    for field in frame.fields:
                        found_fields.append(f"{field.name}: {field.value}")
                    
                    print(" | ".join(found_fields))
                    
                    count += 1
                    if count >= 5: # Only show first 5 records then stop
                        break
                        
    except Exception as e:
        print(f"CRASHED: {e}")

if __name__ == "__main__":
    inspect_first_file()