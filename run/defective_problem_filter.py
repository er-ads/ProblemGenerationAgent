import json
import glob
import os
from datetime import datetime

class DefectiveProblemFilter:
    """
    Filters out problems with 0 or 1 formulas from chapter JSONs
    and consolidates them into a global_defective_problems.json file.
    """
    
    def __init__(self, data_folder_path, output_folder_path=None):
        """
        Initialize the filter.
        
        Args:
            data_folder_path: Path to folder containing chapter JSON files
            output_folder_path: Path where cleaned files will be saved (default: same as input)
        """
        self.data_folder = data_folder_path
        self.output_folder = output_folder_path if output_folder_path else data_folder_path
        self.defective_problems = []
        self.statistics = {
            'total_files_processed': 0,
            'total_problems_original': 0,
            'total_defective_found': 0,
            'total_problems_after_cleaning': 0,
            'chapter_breakdown': {}
        }
        
    def process_all_files(self):
        """Main method to process all chapter files."""
        if not os.path.exists(self.data_folder):
            print(f"❌ Folder not found: {self.data_folder}")
            return False
        
        # Create output folder if it doesn't exist
        if not os.path.exists(self.output_folder):
            os.makedirs(self.output_folder)
            print(f"📁 Created output folder: {self.output_folder}")
        
        json_files = glob.glob(os.path.join(self.data_folder, "*.json"))
        
        # Exclude the defective problems file if it already exists
        json_files = [f for f in json_files if not f.endswith('global_defective_problems.json')]
        
        if not json_files:
            print(f"❌ No JSON files found in: {self.data_folder}")
            return False
        
        print(f"\n{'='*70}")
        print(f"🔍 DEFECTIVE PROBLEM FILTER - Started")
        print(f"{'='*70}")
        print(f"📂 Input Folder: {self.data_folder}")
        print(f"📂 Output Folder: {self.output_folder}")
        print(f"📄 Found {len(json_files)} chapter files to process\n")
        
        # Process each file
        for file_path in sorted(json_files):
            self._process_single_file(file_path)
        
        # Save defective problems
        self._save_defective_problems()
        
        # Print summary
        self._print_summary()
        
        return True
    
    def _process_single_file(self, file_path):
        """Process a single chapter JSON file."""
        file_name = os.path.basename(file_path)
        chapter_name = file_name.replace('.json', '')
        
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
            
            # Handle both list and single dict formats
            if isinstance(data, dict):
                data = [data]
            
            original_count = len(data)
            self.statistics['total_problems_original'] += original_count
            self.statistics['total_files_processed'] += 1
            
            # Separate valid and defective problems
            valid_problems = []
            defective_problems = []
            
            for problem in data:
                formula_ids = problem.get('formula_ids', [])
                num_formulas = len(formula_ids) if formula_ids else 0
                
                if num_formulas <= 1:
                    # Mark as defective and add metadata
                    problem['defect_reason'] = f'insufficient_formulas_{num_formulas}'
                    problem['original_chapter'] = chapter_name
                    problem['filtered_at'] = datetime.now().isoformat()
                    defective_problems.append(problem)
                else:
                    valid_problems.append(problem)
            
            defective_count = len(defective_problems)
            valid_count = len(valid_problems)
            
            # Update statistics
            self.statistics['total_defective_found'] += defective_count
            self.statistics['total_problems_after_cleaning'] += valid_count
            self.statistics['chapter_breakdown'][chapter_name] = {
                'original': original_count,
                'defective': defective_count,
                'valid': valid_count,
                'defect_rate': round((defective_count / original_count * 100), 2) if original_count > 0 else 0
            }
            
            # Add defective problems to global list
            self.defective_problems.extend(defective_problems)
            
            # Save cleaned file (only if there were changes)
            if defective_count > 0:
                output_path = os.path.join(self.output_folder, file_name)
                with open(output_path, 'w') as f:
                    json.dump(valid_problems, f, indent=2)
                
                status = "✓"
                color = "🟢" if defective_count == 0 else "🟡" if defective_count < original_count * 0.1 else "🔴"
            else:
                status = "✓"
                color = "🟢"
            
            print(f"{status} {color} {chapter_name:40} | Original: {original_count:4} | Defective: {defective_count:4} | Valid: {valid_count:4}")
            
        except Exception as e:
            print(f"❌ Error processing {file_name}: {e}")
    
    def _save_defective_problems(self):
        """Save all defective problems to a single JSON file."""
        if not self.defective_problems:
            print("\n✓ No defective problems found!")
            return
        
        output_path = os.path.join(self.output_folder, 'global_defective_problems.json')
        
        # Add metadata to the output
        output_data = {
            'metadata': {
                'total_defective_problems': len(self.defective_problems),
                'generated_at': datetime.now().isoformat(),
                'description': 'Problems with 0 or 1 formulas filtered from chapter files',
                'filter_criteria': 'formula_count <= 1'
            },
            'problems': self.defective_problems
        }
        
        with open(output_path, 'w') as f:
            json.dump(output_data, f, indent=2)
        
        print(f"\n💾 Saved {len(self.defective_problems)} defective problems to: {output_path}")
    
    def _print_summary(self):
        """Print detailed summary of the filtering operation."""
        stats = self.statistics
        
        print(f"\n{'='*70}")
        print(f"📊 SUMMARY")
        print(f"{'='*70}")
        print(f"Files Processed:           {stats['total_files_processed']}")
        print(f"Total Problems (Original): {stats['total_problems_original']}")
        print(f"Defective Problems Found:  {stats['total_defective_found']} ({round(stats['total_defective_found']/stats['total_problems_original']*100, 2)}%)")
        print(f"Valid Problems Remaining:  {stats['total_problems_after_cleaning']}")
        
        print(f"\n{'='*70}")
        print(f"📈 CHAPTER BREAKDOWN")
        print(f"{'='*70}")
        print(f"{'Chapter':<40} | {'Original':>8} | {'Defective':>10} | {'Valid':>8} | {'Defect %':>9}")
        print(f"{'-'*70}")
        
        for chapter, data in sorted(stats['chapter_breakdown'].items()):
            print(f"{chapter:<40} | {data['original']:>8} | {data['defective']:>10} | {data['valid']:>8} | {data['defect_rate']:>8.2f}%")
        
        print(f"{'='*70}")
        
        # Highlight chapters with high defect rates
        high_defect_chapters = [
            (ch, data['defect_rate']) 
            for ch, data in stats['chapter_breakdown'].items() 
            if data['defect_rate'] > 10
        ]
        
        if high_defect_chapters:
            print(f"\n⚠️  CHAPTERS WITH HIGH DEFECT RATES (>10%):")
            for chapter, rate in sorted(high_defect_chapters, key=lambda x: x[1], reverse=True):
                print(f"   • {chapter}: {rate:.2f}%")
        
        print(f"\n✅ Filtering complete!")
    
    def get_statistics(self):
        """Return statistics dictionary."""
        return self.statistics


# ========== MAIN EXECUTION ==========

if __name__ == "__main__":
    # Configuration
    INPUT_FOLDER = "chapterwise_generated_dataset"  # Change this to your input folder
    OUTPUT_FOLDER = None  # Change this to your output folder (or None for in-place)
    
    # You can set OUTPUT_FOLDER to None to overwrite the original files
    # OUTPUT_FOLDER = None
    
    print("""
╔══════════════════════════════════════════════════════════════════════╗
║                   DEFECTIVE PROBLEM FILTER                           ║
║                                                                      ║
║  This script identifies and removes problems with ≤1 formulas       ║
║  from chapter JSON files and consolidates them into a single file   ║
╚══════════════════════════════════════════════════════════════════════╝
    """)
    
    # Create filter instance
    filter_tool = DefectiveProblemFilter(
        data_folder_path=INPUT_FOLDER,
        output_folder_path=OUTPUT_FOLDER
    )
    
    # Process all files
    success = filter_tool.process_all_files()
    
    if success:
        print(f"\n🎉 All done! Check the output folder for cleaned files.")
        print(f"   Defective problems saved to: global_defective_problems.json")
    else:
        print(f"\n❌ Processing failed. Please check the error messages above.")
