import os
import argparse
import pandas as pd

def convert_json_to_excel(json_path, excel_path):
    print(f"Reading JSON file: {json_path}")
    if not os.path.exists(json_path):
        print(f"Error: File '{json_path}' does not exist!")
        return

    try:
        # Load JSON data
        df = pd.read_json(json_path)
        
        # Write to Excel
        print(f"Writing data to Excel: {excel_path}")
        
        # We use ExcelWriter to format columns to look clean and legible
        with pd.ExcelWriter(excel_path, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Hotels')
            
            # Auto-fit columns
            workbook = writer.book
            worksheet = writer.sheets['Hotels']
            for col in worksheet.columns:
                max_len = max(len(str(val.value or '')) for val in col)
                col_letter = col[0].column_letter
                # Set a reasonable min/max width
                worksheet.column_dimensions[col_letter].width = min(max(max_len + 3, 10), 50)
                
        print(f"Successfully converted! Excel file saved at: {excel_path}")
        try:
            os.chmod(excel_path, 0o666)
        except Exception:
            pass
    except Exception as e:
        print(f"An error occurred during conversion: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Convert scraped hotel JSON files to Excel (.xlsx) sheets")
    parser.add_argument(
        "--input", 
        type=str, 
        default="makemytrip_hotels.json",
        help="Input JSON file path"
    )
    parser.add_argument(
        "--output", 
        type=str, 
        help="Output Excel file path (defaults to same name with .xlsx)"
    )
    
    args = parser.parse_args()
    
    # Default output path configuration
    if not args.output:
        base_name, _ = os.path.splitext(args.input)
        args.output = base_name + ".xlsx"
        
    convert_json_to_excel(args.input, args.output)
