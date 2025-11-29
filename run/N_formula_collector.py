import json
import glob
import os
from datetime import datetime

class NFormulaProblemCollector:
    """
    Collects all problems with exactly N formulas from chapter JSONs
    and consolidates them into a global_{n}_formula_count.json file.
    Original files remain unchanged.
    """
    
    def __init__(self, data_folder_path, target_count, output_file_path=None):
        """
        Initialize the collector.
        
        Args:
            data_folder_path: Path to folder containing chapter JSON files
            target_count: Integer representing the exact number of formulas to filter for
            output_file_path: Path where collected file will be saved (default: auto-generated)
        """
        self.data_folder = data_folder_path
        self.target_count = int(target_count)
        
        # Auto-generate filename if not provided: e.g., global_3_formula_count.json
        default_filename = f'global_{self.target_count}_formula_count.json'
        
        self.output_file_path = output_file_path if output_file_path else os.path.join(
            data_folder_path, default_filename
        )
        
        self.collected_problems = []
        self.statistics = {
            'total_files_processed': 0,
            'total_problems_scanned': 0,
            'total_matches_found': 0,
            'chapter_breakdown': {}
        }
        
    def collect_all_files(self):
        """Main method to collect from all chapter files."""
        if not os.path.exists(self.data_folder):
            print(f"❌ Folder not found: {self.data_folder}")
            return False
        
        json_files = glob.glob(os.path.join(self.data_folder, "*.json"))
        
        # Exclude output files if they already exist to avoid recursion
        current_output_name = os.path.basename(self.output_file_path)
        json_files = [f for f in json_files if not any(
            f.endswith(name) for name in [
                current_output_name,
                'global_defective_problems.json'
            ]
        )]
        
        if not json_files:
            print(f"❌ No JSON files found in: {self.data_folder}")
            return False
        
        print(f"\n{'='*70}")
        print(f"🔍 {self.target_count}-FORMULA PROBLEM COLLECTOR - Started")
        print(f"{'='*70}")
        print(f"📂 Input Folder: {self.data_folder}")
        print(f"🎯 Target Formula Count: {self.target_count}")
        print(f"📄 Output File: {self.output_file_path}")
        print(f"📄 Found {len(json_files)} chapter files to scan\n")
        
        # Process each file
        for file_path in sorted(json_files):
            self._process_single_file(file_path)
        
        # Save collected problems
        self._save_collected_problems()
        
        # Print summary
        self._print_summary()
        
        return True
    
    def _process_single_file(self, file_path):
        """Process a single chapter JSON file (read-only)."""
        file_name = os.path.basename(file_path)
        chapter_name = file_name.replace('.json', '')
        
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
            
            # Handle both list and single dict formats
            if isinstance(data, dict):
                data = [data]
            
            total_count = len(data)
            self.statistics['total_problems_scanned'] += total_count
            self.statistics['total_files_processed'] += 1
            
            # Collect problems with exactly N formulas
            matching_problems = []
            
            for problem in data:
                formula_ids = problem.get('formula_ids', [])
                num_formulas = len(formula_ids) if formula_ids else 0
                
                if num_formulas == self.target_count:
                    # Add metadata for tracking
                    problem_copy = problem.copy()
                    problem_copy['source_chapter'] = chapter_name
                    problem_copy['collected_at'] = datetime.now().isoformat()
                    matching_problems.append(problem_copy)
            
            found_count = len(matching_problems)
            
            # Update statistics
            self.statistics['total_matches_found'] += found_count
            self.statistics['chapter_breakdown'][chapter_name] = {
                'total_problems': total_count,
                'match_count': found_count,
                'percentage': round((found_count / total_count * 100), 2) if total_count > 0 else 0
            }
            
            # Add to global collection
            self.collected_problems.extend(matching_problems)
            
            # Display progress
            status = "✓"
            color = "🟢" if found_count > 0 else "⚪"
            
            # Dynamic Label for print
            label = f"{self.target_count}-Formula"
            
            print(f"{status} {color} {chapter_name:40} | Total: {total_count:4} | {label}: {found_count:4} ({self.statistics['chapter_breakdown'][chapter_name]['percentage']:>5.1f}%)")
            
        except Exception as e:
            print(f"❌ Error processing {file_name}: {e}")
    
    def _save_collected_problems(self):
        """Save all collected problems to a single JSON file."""
        if not self.collected_problems:
            print(f"\n✓ No problems with exactly {self.target_count} formulas found!")
            return
        
        # Add metadata to the output
        output_data = {
            'metadata': {
                'total_problems_collected': len(self.collected_problems),
                'target_formula_count': self.target_count,
                'generated_at': datetime.now().isoformat(),
                'description': f'Problems with exactly {self.target_count} formulas collected from chapter files',
                'collection_criteria': f'formula_count == {self.target_count}',
                'note': 'Original chapter files remain unchanged'
            },
            'problems': self.collected_problems
        }
        
        with open(self.output_file_path, 'w') as f:
            json.dump(output_data, f, indent=2)
        
        print(f"\n💾 Saved {len(self.collected_problems)} problems to: {self.output_file_path}")
    
    def _print_summary(self):
        """Print detailed summary of the collection operation."""
        stats = self.statistics
        n = self.target_count
        
        print(f"\n{'='*70}")
        print(f"📊 SUMMARY")
        print(f"{'='*70}")
        print(f"Files Scanned:              {stats['total_files_processed']}")
        print(f"Total Problems Scanned:     {stats['total_problems_scanned']}")
        print(f"{n}-Formula Problems Found:   {stats['total_matches_found']} ({round(stats['total_matches_found']/stats['total_problems_scanned']*100, 2) if stats['total_problems_scanned'] > 0 else 0}%)")
        
        print(f"\n{'='*70}")
        print(f"📈 CHAPTER BREAKDOWN")
        print(f"{'='*70}")
        
        col_header = f"{n}-Formula"
        print(f"{'Chapter':<40} | {'Total':>8} | {col_header:>10} | {'Percentage':>11}")
        print(f"{'-'*70}")
        
        for chapter, data in sorted(stats['chapter_breakdown'].items()):
            print(f"{chapter:<40} | {data['total_problems']:>8} | {data['match_count']:>10} | {data['percentage']:>10.2f}%")
        
        print(f"{'='*70}")
        
        # Highlight chapters with high concentration
        high_concentration = [
            (ch, data['percentage']) 
            for ch, data in stats['chapter_breakdown'].items() 
            if data['percentage'] > 50 and data['match_count'] > 0
        ]
        
        if high_concentration:
            print(f"\n📌 CHAPTERS WITH HIGH {n}-FORMULA CONCENTRATION (>50%):")
            for chapter, percentage in sorted(high_concentration, key=lambda x: x[1], reverse=True):
                print(f"   • {chapter}: {percentage:.2f}%")
        
        # Show chapters with no matches
        no_matches = [
            ch for ch, data in stats['chapter_breakdown'].items() 
            if data['match_count'] == 0
        ]
        
        if no_matches:
            print(f"\n⚪ CHAPTERS WITH NO {n}-FORMULA PROBLEMS:")
            for chapter in no_matches:
                print(f"   • {chapter}")
        
        print(f"\n✅ Collection complete! Original files unchanged.")
    
    def get_statistics(self):
        """Return statistics dictionary."""
        return self.statistics
    
    def get_collected_problems(self):
        """Return list of collected problems."""
        return self.collected_problems


# ========== MAIN EXECUTION ==========

if __name__ == "__main__":
    # Configuration
    INPUT_FOLDER = "chapterwise_generated_dataset"  # Change this to your input folder
    
    # !!! SET YOUR TARGET NUMBER OF FORMULAS HERE !!!
    TARGET_FORMULA_COUNT = 2 
    
    OUTPUT_FILE = None  # None = save to INPUT_FOLDER/global_{N}_formula_count.json
    
    print(f"""
╔══════════════════════════════════════════════════════════════════════╗
║               {TARGET_FORMULA_COUNT}-FORMULA PROBLEM COLLECTOR                          ║
║                                                                      ║
║  This script collects all problems with exactly {TARGET_FORMULA_COUNT} formulas          ║
║  and saves them to global_{TARGET_FORMULA_COUNT}_formula_count.json                      ║
║  Original chapter files remain completely unchanged.                ║
╚══════════════════════════════════════════════════════════════════════╝
    """)
    
    # Create collector instance
    collector = NFormulaProblemCollector(
        data_folder_path=INPUT_FOLDER,
        target_count=TARGET_FORMULA_COUNT,
        output_file_path=OUTPUT_FILE
    )
    
    # Collect from all files
    success = collector.collect_all_files()
    
    if success:
        stats = collector.get_statistics()
        print(f"\n🎉 All done! Collected {stats['total_matches_found']} problems with {TARGET_FORMULA_COUNT} formulas.")
        print(f"   Output file: {collector.output_file_path}")
        print(f"   Original chapter files: UNCHANGED ✓")
    else:
        print(f"\n❌ Collection failed. Please check the error messages above.")