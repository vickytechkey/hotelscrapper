import os
import argparse
import json
import openpyxl

def convert_json_to_excel(json_path, excel_path):
    print(f"Reading JSON file: {json_path}")
    if not os.path.exists(json_path):
        print(f"Error: File '{json_path}' does not exist!")
        return

    try:
        # Load JSON data safely using standard library
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        if not data:
            print("Warning: JSON data is empty!")
            return
            
        # Write to Excel
        print(f"Writing data to Excel: {excel_path}")
        
        # Create Excel workbook using pure openpyxl (bypasses pandas/pyarrow)
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Hotels"
        
        # Extract headers (all unique keys)
        headers = []
        for item in data:
            for k in item.keys():
                if k not in headers:
                    headers.append(k)
                    
        # Write headers
        ws.append(headers)
        
        # Write rows
        for item in data:
            row = [item.get(h, "") for h in headers]
            ws.append(row)
            
        # Auto-fit columns
        for col in ws.columns:
            max_len = max(len(str(val.value or '')) for val in col)
            col_letter = col[0].column_letter
            ws.column_dimensions[col_letter].width = min(max(max_len + 3, 10), 50)
            
        wb.save(excel_path)
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
