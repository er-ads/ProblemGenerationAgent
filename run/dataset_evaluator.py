import json
import numpy as np
# add explicit Agg backend to avoid display backend errors on headless systems
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from collections import Counter
import glob
import os
import base64
from io import BytesIO
import re

class PhysicsDatasetEvaluator:
    """
    Combined Evaluator: Calculates detailed metrics and generates a self-contained HTML report.
    """
    
    def __init__(self, data_folder_path):
        self.data_folder = data_folder_path
        self.chapter_data = {} 
        self.all_data = []     
        self.results = {
            'global': {},
            'chapters': {}
        }
        self._load_data()
        
    def _load_data(self):
        """Auto-detect and load all JSON files in the folder."""
        if not os.path.exists(self.data_folder):
            print(f"❌ Folder not found: {self.data_folder}")
            return

        json_files = glob.glob(os.path.join(self.data_folder, "*.json"))
        print(f"📂 Found {len(json_files)} chapter files in '{self.data_folder}'")
        
        for file_path in json_files:
            file_name = os.path.basename(file_path).replace('.json', '')
            try:
                with open(file_path, 'r') as f:
                    data = json.load(f)
                    if isinstance(data, dict): data = [data]
                    self.chapter_data[file_name] = data
                    self.all_data.extend(data)
                    print(f"   - Loaded {file_name}: {len(data)} problems")
            except Exception as e:
                print(f"   ⚠️ Error loading {file_name}: {e}")

    def evaluate_all(self):
        """Run all intrinsic evaluations."""
        if not self.all_data:
            print("❌ No data loaded. Please check your folder path.")
            return None

        print("\n🔍 Starting Evaluation...")
        
        # 1. Evaluate Each Chapter
        sorted_chapters = sorted(self.chapter_data.keys())
        for chapter_name in sorted_chapters:
            subset_data = self.chapter_data[chapter_name]
            self.results['chapters'][chapter_name] = self._compute_metrics_for_subset(subset_data)

        # 2. Evaluate Global Dataset
        self.results['global'] = self._compute_metrics_for_subset(self.all_data)
        
        print("✅ Evaluation metrics calculated.")
        return self.results

    def _compute_metrics_for_subset(self, data_subset):
        """Core logic to compute all metrics for a given list of problems."""
        if not data_subset: return {}

        # Extract basic lists
        results_list = [d.get('result') for d in data_subset if d.get('result') is not None]
        code_lengths = [len(d.get('code', '')) for d in data_subset]
        texts = [d.get('word_problem', '') for d in data_subset]
        signatures = [d.get('signature', '') for d in data_subset]
        
        all_formulas = []
        formula_counts_per_prob = []
        unknowns = []
        
        # New: Track formula count vs code length
        formula_count_to_code_lengths = {}
        formula_count_distribution = {}
        
        for d in data_subset:
            fids = d.get('formula_ids', [])
            all_formulas.extend(fids)
            num_formulas = len(fids)
            formula_counts_per_prob.append(num_formulas)
            unknowns.append(d.get('unknown_var', 'N/A'))
            
            # Track distribution
            formula_count_distribution[num_formulas] = formula_count_distribution.get(num_formulas, 0) + 1
            
            # Track code length by formula count
            code_len = len(d.get('code', ''))
            if num_formulas not in formula_count_to_code_lengths:
                formula_count_to_code_lengths[num_formulas] = []
            formula_count_to_code_lengths[num_formulas].append(code_len)

        # Calculate average code length per formula count
        avg_code_length_by_formula_count = {
            fc: round(np.mean(lengths), 1) 
            for fc, lengths in formula_count_to_code_lengths.items()
        }

        # 1. Numerical Validity
        # Safely coerce results_list items to float where possible; ignore non-convertible
        results_arr = np.array([], dtype=float)
        if results_list:
            cleaned = []
            for x in results_list:
                try:
                    cleaned.append(float(x))
                except Exception:
                    continue
            results_arr = np.array(cleaned, dtype=float) if cleaned else np.array([], dtype=float)
        
        unrealistic = 0
        if len(results_arr) > 0:
            unrealistic = np.sum((np.abs(results_arr) > 1e15) | (np.abs(results_arr) < 1e-15))
        
        # 2. Distinctness (Text & Signature)
        unique_texts = set(texts)
        unique_signatures = set(signatures)
        text_uniqueness = (len(unique_texts) / len(texts) * 100) if texts else 0
        sig_uniqueness = (len(unique_signatures) / len(signatures) * 100) if signatures else 0

        # 3. Difficulty & Balance
        formula_freq = Counter(all_formulas)
        unknown_freq = Counter(unknowns)
        avg_complexity = np.mean(formula_counts_per_prob) if formula_counts_per_prob else 0
        
        # 4. Text Diversity (Type-Token Ratio)
        all_tokens = []
        for t in texts: all_tokens.extend(t.lower().split())
        ttr = (len(set(all_tokens)) / len(all_tokens) * 100) if all_tokens else 0

        return {
            'size': len(data_subset),
            'numerical_quality': {
                'valid_results_pct': round((len(results_list)/len(data_subset))*100, 1),
                'unrealistic_values': int(unrealistic),
            },
            'distinctness': {
                'text_uniqueness_pct': round(text_uniqueness, 2),
                'signature_uniqueness_pct': round(sig_uniqueness, 2),
                'duplicate_texts': len(texts) - len(unique_texts)
            },
            'code_stats': {
                'avg_char_length': round(np.mean(code_lengths), 1) if code_lengths else 0
            },
            'difficulty': {
                'avg_formulas_per_prob': round(avg_complexity, 2),
                'level': self._assess_difficulty(avg_complexity)
            },
            'content_balance': {
                'unique_formulas_used': len(formula_freq),
                'unique_unknowns_used': len(unknown_freq),
                'top_15_formulas': dict(formula_freq.most_common(15)),
                'top_10_unknowns': dict(unknown_freq.most_common(10))
            },
            'generation_quality': {
                'type_token_ratio': round(ttr, 2),
                'avg_word_count': round(len(all_tokens)/len(texts), 1) if texts else 0
            },
            'formula_analysis': {
                'formula_count_distribution': dict(sorted(formula_count_distribution.items())),
                'avg_code_length_by_formula_count': dict(sorted(avg_code_length_by_formula_count.items()))
            }
        }

    def _assess_difficulty(self, val):
        """String labels for difficulty based on formula count."""
        if val >= 3.0: return "Hard (n>3)"
        elif val >= 2.0: return "Medium (n=2)"
        else: return "Easy"

    def sanitize_id(self, name):
        """Convert chapter name to safe HTML id."""
        return re.sub(r'[^a-zA-Z0-9_-]', '_', name)

    # ========== PLOT GENERATION ==========

    def generate_chapter_plot(self, chapter_metrics):
        """Generate per-chapter visualization (Top formulas + Top unknowns + Formula analysis)."""
        fig = plt.figure(figsize=(12, 10))
        gs = fig.add_gridspec(3, 2, height_ratios=[1, 1, 1])

        # Modern Tech color scheme
        primary_color = '#8B5CF6'  # Vibrant Purple
        accent_color = '#10B981'   # Emerald Green
        dark_color = '#4C1D95'     # Deep Violet

        # Top formulas (limit to top 10)
        ax1 = fig.add_subplot(gs[0, :])
        formulas = chapter_metrics['content_balance']['top_15_formulas']
        if formulas:
            keys = list(formulas.keys())[:10]
            vals = list(formulas.values())[:10]
            ax1.bar(keys, vals, color=primary_color, edgecolor=dark_color, linewidth=1)
            ax1.set_title('Top 10 Formulas', fontsize=10, fontweight='bold', color=dark_color)
            ax1.tick_params(axis='x', rotation=45, labelsize=8)
            ax1.set_ylabel('Frequency', fontsize=9, fontweight='600')
            ax1.grid(axis='y', alpha=0.25, linestyle='--', color='#94A3B8')
            ax1.set_facecolor('#FAFAFA')

        # Formula Count Distribution
        ax2 = fig.add_subplot(gs[1, 0])
        formula_dist = chapter_metrics['formula_analysis']['formula_count_distribution']
        if formula_dist:
            counts = list(formula_dist.keys())
            problems = list(formula_dist.values())
            bars = ax2.bar(counts, problems, color=primary_color, edgecolor=dark_color, linewidth=1, width=0.6)
            ax2.set_title('Problem Distribution by Formula Count', fontsize=10, fontweight='bold', color=dark_color)
            ax2.set_xlabel('Number of Formulas', fontsize=9, fontweight='600')
            ax2.set_ylabel('Number of Problems', fontsize=9, fontweight='600')
            ax2.grid(axis='y', alpha=0.25, linestyle='--', color='#94A3B8')
            ax2.set_facecolor('#FAFAFA')
            # Add value labels
            for bar in bars:
                height = bar.get_height()
                ax2.text(bar.get_x() + bar.get_width()/2., height,
                        f'{int(height)}', ha='center', va='bottom', fontsize=7, fontweight='600')

        # Avg Code Length by Formula Count
        ax3 = fig.add_subplot(gs[1, 1])
        code_by_formula = chapter_metrics['formula_analysis']['avg_code_length_by_formula_count']
        if code_by_formula:
            formula_counts = list(code_by_formula.keys())
            avg_lengths = list(code_by_formula.values())
            ax3.plot(formula_counts, avg_lengths, marker='o', color=accent_color, 
                    linewidth=2.5, markersize=8, markerfacecolor=accent_color, 
                    markeredgecolor='#059669', markeredgewidth=1.5)
            ax3.set_title('Avg Code Length vs Formula Count', fontsize=10, fontweight='bold', color=dark_color)
            ax3.set_xlabel('Number of Formulas', fontsize=9, fontweight='600')
            ax3.set_ylabel('Avg Code Length (chars)', fontsize=9, fontweight='600')
            ax3.grid(True, alpha=0.25, linestyle='--', color='#94A3B8')
            ax3.set_facecolor('#FAFAFA')
            # Add value labels
            for x, y in zip(formula_counts, avg_lengths):
                ax3.text(x, y + max(avg_lengths)*0.02, f'{y:.0f}', 
                        ha='center', va='bottom', fontsize=7, fontweight='600')

        # Top unknowns
        ax4 = fig.add_subplot(gs[2, :])
        unknowns = chapter_metrics['content_balance']['top_10_unknowns']
        if unknowns:
            ax4.barh(list(unknowns.keys()), list(unknowns.values()), color=accent_color, edgecolor='#059669', linewidth=1)
            ax4.set_title('Top 10 Unknown Variables', fontsize=10, fontweight='bold', color=dark_color)
            ax4.invert_yaxis()
            ax4.tick_params(axis='both', labelsize=8)
            ax4.set_xlabel('Frequency', fontsize=9, fontweight='600')
            ax4.grid(axis='x', alpha=0.25, linestyle='--', color='#94A3B8')
            ax4.set_facecolor('#FAFAFA')

        plt.tight_layout()
        
        # Save to buffer
        buf = BytesIO()
        plt.savefig(buf, format='png', dpi=100)
        plt.close(fig)
        return base64.b64encode(buf.getvalue()).decode('utf-8')

    def _generate_plots_base64(self):
        """Generate all plots and return dict with global and per-chapter plots."""
        plot_dict = {'global': '', 'chapters': {}}
        
        # Generate global plots with Modern Tech color scheme
        fig = plt.figure(figsize=(16, 16))
        gs = fig.add_gridspec(4, 2, height_ratios=[1, 1, 1, 1])

        # Color palette: Modern Tech
        primary_color = '#8B5CF6'  # Vibrant Purple
        accent_color = '#10B981'   # Emerald Green
        dark_color = '#4C1D95'     # Deep Violet

        # 1. Formulas per Chapter (Bar Chart)
        ax0 = fig.add_subplot(gs[0, :])
        chapters = sorted(self.results['chapters'].keys())
        formula_counts = [self.results['chapters'][c]['content_balance']['unique_formulas_used'] 
                         for c in chapters]
        
        bars = ax0.bar(chapters, formula_counts, color=primary_color, edgecolor=dark_color, linewidth=1.5)
        ax0.set_ylabel('Unique Formulas Used', fontsize=11, fontweight='600')
        ax0.set_title('Formulas per Chapter', fontsize=13, fontweight='bold', color=dark_color)
        ax0.tick_params(axis='x', rotation=45, labelsize=9)
        ax0.grid(axis='y', alpha=0.25, linestyle='--', color='#94A3B8')
        ax0.set_facecolor('#FAFAFA')
        
        # Add value labels on bars
        for bar in bars:
            height = bar.get_height()
            ax0.text(bar.get_x() + bar.get_width()/2., height,
                    f'{int(height)}', ha='center', va='bottom', fontsize=8, fontweight='600')

        # 2. Global Formula Count Distribution
        ax1 = fig.add_subplot(gs[1, 0])
        formula_dist = self.results['global']['formula_analysis']['formula_count_distribution']
        if formula_dist:
            counts = list(formula_dist.keys())
            problems = list(formula_dist.values())
            bars = ax1.bar(counts, problems, color=primary_color, edgecolor=dark_color, linewidth=1.5, width=0.6)
            ax1.set_title('Global: Problems by Formula Count', fontsize=11, fontweight='bold', color=dark_color)
            ax1.set_xlabel('Number of Formulas in Problem', fontsize=10, fontweight='600')
            ax1.set_ylabel('Number of Problems', fontsize=10, fontweight='600')
            ax1.grid(axis='y', alpha=0.25, linestyle='--', color='#94A3B8')
            ax1.set_facecolor('#FAFAFA')
            # Add value labels
            for bar in bars:
                height = bar.get_height()
                ax1.text(bar.get_x() + bar.get_width()/2., height,
                        f'{int(height)}', ha='center', va='bottom', fontsize=8, fontweight='600')

        # 3. Global Avg Code Length by Formula Count
        ax2 = fig.add_subplot(gs[1, 1])
        code_by_formula = self.results['global']['formula_analysis']['avg_code_length_by_formula_count']
        if code_by_formula:
            formula_counts_global = list(code_by_formula.keys())
            avg_lengths_global = list(code_by_formula.values())
            ax2.plot(formula_counts_global, avg_lengths_global, marker='o', color=accent_color, 
                    linewidth=3, markersize=10, markerfacecolor=accent_color, 
                    markeredgecolor='#059669', markeredgewidth=2)
            ax2.set_title('Global: Avg Code Length vs Formula Count', fontsize=11, fontweight='bold', color=dark_color)
            ax2.set_xlabel('Number of Formulas', fontsize=10, fontweight='600')
            ax2.set_ylabel('Avg Code Length (chars)', fontsize=10, fontweight='600')
            ax2.grid(True, alpha=0.25, linestyle='--', color='#94A3B8')
            ax2.set_facecolor('#FAFAFA')
            # Add value labels
            for x, y in zip(formula_counts_global, avg_lengths_global):
                ax2.text(x, y + max(avg_lengths_global)*0.02, f'{y:.0f}', 
                        ha='center', va='bottom', fontsize=8, fontweight='600')

        # 4. Chapter Comparison: Difficulty vs Diversity
        ax3 = fig.add_subplot(gs[2, 0])
        diffs = [self.results['chapters'][c]['difficulty']['avg_formulas_per_prob'] for c in chapters]
        ttrs = [self.results['chapters'][c]['generation_quality']['type_token_ratio'] for c in chapters]
        
        x = np.arange(len(chapters))
        width = 0.35
        ax3.bar(x - width/2, diffs, width, label='Avg Formulas', color=primary_color, edgecolor=dark_color, linewidth=1)
        ax4 = ax3.twinx()
        ax4.bar(x + width/2, ttrs, width, label='TTR %', color=accent_color, edgecolor='#059669', linewidth=1)
        
        ax3.set_ylabel('Avg Formulas', fontsize=10, fontweight='600')
        ax4.set_ylabel('Type-Token Ratio (%)', fontsize=10, fontweight='600')
        ax3.set_title('Chapter Analysis: Complexity vs Diversity', fontsize=11, fontweight='bold', color=dark_color)
        ax3.set_xticks(x)
        ax3.set_xticklabels(chapters, rotation=45, ha='right', fontsize=8)
        ax3.legend(loc='upper left', fontsize=8)
        ax4.legend(loc='upper right', fontsize=8)
        ax3.grid(axis='y', alpha=0.25, linestyle='--', color='#94A3B8')
        ax3.set_facecolor('#FAFAFA')

        # 5. Global Top Formulas
        ax5 = fig.add_subplot(gs[2, 1])
        formulas = self.results['global']['content_balance']['top_15_formulas']
        if formulas:
            keys = list(formulas.keys())[:10]
            vals = list(formulas.values())[:10]
            ax5.bar(keys, vals, color=primary_color, edgecolor=dark_color, linewidth=1)
            ax5.set_title('Top 10 Formulas (Global)', fontsize=11, fontweight='bold', color=dark_color)
            ax5.tick_params(axis='x', rotation=45, labelsize=8)
            ax5.set_ylabel('Frequency', fontsize=10, fontweight='600')
            ax5.grid(axis='y', alpha=0.25, linestyle='--', color='#94A3B8')
            ax5.set_facecolor('#FAFAFA')

        # 6. Global Top Unknowns
        ax6 = fig.add_subplot(gs[3, :])
        unknowns = self.results['global']['content_balance']['top_10_unknowns']
        if unknowns:
            ax6.barh(list(unknowns.keys()), list(unknowns.values()), color=accent_color, edgecolor='#059669', linewidth=1)
            ax6.set_title('Top 10 Unknown Variables (Global)', fontsize=11, fontweight='bold', color=dark_color)
            ax6.invert_yaxis()
            ax6.set_xlabel('Frequency', fontsize=10, fontweight='600')
            ax6.grid(axis='x', alpha=0.25, linestyle='--', color='#94A3B8')
            ax6.set_facecolor('#FAFAFA')

        plt.tight_layout()
        
        # Save global plot
        buf = BytesIO()
        plt.savefig(buf, format='png', dpi=100)
        plt.close(fig)
        plot_dict['global'] = base64.b64encode(buf.getvalue()).decode('utf-8')
        
        # Generate per-chapter plots
        for chapter, metrics in self.results['chapters'].items():
            plot_dict['chapters'][chapter] = self.generate_chapter_plot(metrics)
        
        return plot_dict

    def _generate_plots_base64_global(self):
        """Backward compatibility: return only global plot as base64 string."""
        plot_dict = self._generate_plots_base64()
        return plot_dict['global']

    # ========== REPORT GENERATION ==========

    def generate_report(self, output_file='Physics_Evaluation_Report.html'):
        """Orchestrates the creation of the HTML report."""
        if not self.results['global']:
            print("❌ Cannot generate report: No results found.")
            return

        print("📊 Generating visualizations and HTML report...")
        plot_dict = self._generate_plots_base64()
        html_content = self._generate_html_content(plot_dict)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(html_content)
        print(f"✓ Report saved to: {output_file}")

    def _generate_html_content(self, plot_dict):
        """Constructs the HTML string with interactive chapter panels."""
        g_res = self.results['global']
        
        # HTML Header & CSS
        html = """
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Physics Dataset Evaluation Report</title>
            <style>
                * { margin: 0; padding: 0; box-sizing: border-box; }
                
                body { 
                    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                    background: #F3F4F6;
                    min-height: 100vh;
                    padding: 40px 20px;
                    color: #1F2937;
                    line-height: 1.6;
                }
                
                .container { 
                    max-width: 1400px;
                    margin: 0 auto;
                    background: #ffffff;
                    border-radius: 20px;
                    box-shadow: 0 20px 60px rgba(76, 29, 149, 0.15);
                    overflow: hidden;
                }
                
                .header {
                    background: linear-gradient(135deg, #4C1D95 0%, #8B5CF6 100%);
                    color: white;
                    padding: 50px 40px;
                    text-align: center;
                }
                
                .header h1 { 
                    font-size: 2.5em;
                    font-weight: 700;
                    margin-bottom: 10px;
                    text-shadow: 0 2px 4px rgba(0,0,0,0.2);
                }
                
                .header p {
                    font-size: 1.1em;
                    opacity: 0.95;
                }
                
                .content {
                    padding: 40px;
                }
                
                h2 { 
                    color: #4C1D95;
                    font-size: 1.8em;
                    font-weight: 700;
                    margin: 40px 0 20px 0;
                    padding-bottom: 10px;
                    border-bottom: 3px solid #8B5CF6;
                    display: inline-block;
                }
                
                .metric-grid { 
                    display: grid;
                    grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
                    gap: 20px;
                    margin: 30px 0;
                }
                
                .card { 
                    background: #ffffff;
                    padding: 25px;
                    border-radius: 12px;
                    border: 1px solid #E5E7EB;
                    transition: all 0.3s ease;
                    position: relative;
                    overflow: hidden;
                    box-shadow: 0 2px 4px rgba(0, 0, 0, 0.04);
                }
                
                .card::before {
                    content: '';
                    position: absolute;
                    top: 0;
                    left: 0;
                    width: 4px;
                    height: 100%;
                    background: #8B5CF6;
                }
                
                .card:hover { 
                    transform: translateY(-5px);
                    box-shadow: 0 12px 24px rgba(76, 29, 149, 0.15);
                    border-color: #8B5CF6;
                }
                
                .card h3 { 
                    font-size: 0.8em;
                    color: #4A5568;
                    text-transform: uppercase;
                    letter-spacing: 1px;
                    margin-bottom: 12px;
                    font-weight: 700;
                }
                
                .card p { 
                    font-size: 2em;
                    font-weight: 700;
                    color: #8B5CF6;
                }
                
                /* Semantic coloring for problem metrics */
                .card.warning p {
                    color: #F59E0B;
                }
                
                .card.alert p {
                    color: #EF4444;
                }
                
                .card.success p {
                    color: #10B981;
                }
                
                .plot-container { 
                    background: #FAFAFA;
                    border-radius: 15px;
                    padding: 30px;
                    margin: 30px 0;
                    box-shadow: 0 4px 6px rgba(0, 0, 0, 0.05);
                    border: 1px solid #E5E7EB;
                }
                
                .plot-container img { 
                    max-width: 100%;
                    height: auto;
                    border-radius: 10px;
                }
                
                table { 
                    width: 100%;
                    border-collapse: separate;
                    border-spacing: 0;
                    margin-top: 20px;
                    background: white;
                    border-radius: 12px;
                    overflow: hidden;
                    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
                    border: 1px solid #E5E7EB;
                }
                
                th { 
                    background: linear-gradient(135deg, #4C1D95 0%, #8B5CF6 100%);
                    color: white;
                    padding: 18px 15px;
                    text-align: left;
                    font-weight: 700;
                    text-transform: uppercase;
                    font-size: 0.8em;
                    letter-spacing: 0.5px;
                    cursor: pointer;
                    user-select: none;
                    transition: background 0.3s ease;
                }
                
                th:hover { 
                    background: linear-gradient(135deg, #3B1475 0%, #7C3AED 100%);
                }
                
                td { 
                    padding: 16px 15px;
                    border-bottom: 1px solid #E5E7EB;
                    color: #1F2937;
                }
                
                tr:last-child td {
                    border-bottom: none;
                }
                
                .clickable-row { 
                    cursor: pointer;
                    transition: all 0.2s ease;
                }
                
                .clickable-row:hover { 
                    background: linear-gradient(90deg, rgba(139, 92, 246, 0.08) 0%, rgba(16, 185, 129, 0.05) 100%);
                }
                
                .chapter-detail { 
                    display: none;
                    background: #F9FAFB;
                    padding: 30px;
                    margin: 0;
                    border-radius: 0;
                    animation: slideDown 0.3s ease;
                    border-top: 2px solid #8B5CF6;
                }
                
                @keyframes slideDown {
                    from {
                        opacity: 0;
                        transform: translateY(-10px);
                    }
                    to {
                        opacity: 1;
                        transform: translateY(0);
                    }
                }
                
                .chapter-detail.active { 
                    display: block;
                }
                
                .chapter-detail h3 { 
                    color: #4C1D95;
                    font-size: 1.5em;
                    margin-bottom: 25px;
                    font-weight: 700;
                }
                
                .detail-grid { 
                    display: grid;
                    grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
                    gap: 15px;
                    margin-bottom: 25px;
                }
                
                .detail-card { 
                    background: white;
                    padding: 18px;
                    border-radius: 10px;
                    border-left: 3px solid #8B5CF6;
                    box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
                    transition: all 0.3s ease;
                }
                
                .detail-card:hover {
                    transform: translateY(-3px);
                    box-shadow: 0 4px 12px rgba(139, 92, 246, 0.15);
                }
                
                .detail-card h4 { 
                    font-size: 0.75em;
                    color: #4A5568;
                    text-transform: uppercase;
                    letter-spacing: 0.5px;
                    margin-bottom: 8px;
                    font-weight: 700;
                }
                
                .detail-card p { 
                    font-size: 1.5em;
                    font-weight: 700;
                    color: #1F2937;
                }
                
                .controls { 
                    margin: 30px 0 20px 0;
                    display: flex;
                    gap: 12px;
                    flex-wrap: wrap;
                }
                
                .btn { 
                    background: linear-gradient(135deg, #8B5CF6 0%, #4C1D95 100%);
                    color: white;
                    border: none;
                    padding: 12px 24px;
                    border-radius: 8px;
                    cursor: pointer;
                    font-size: 0.95em;
                    font-weight: 600;
                    transition: all 0.3s ease;
                    box-shadow: 0 4px 6px rgba(139, 92, 246, 0.3);
                }
                
                .btn:hover { 
                    transform: translateY(-2px);
                    box-shadow: 0 6px 12px rgba(139, 92, 246, 0.4);
                }
                
                .btn-secondary { 
                    background: linear-gradient(135deg, #6B7280 0%, #4B5563 100%);
                    box-shadow: 0 4px 6px rgba(107, 114, 128, 0.3);
                }
                
                .btn-secondary:hover { 
                    box-shadow: 0 6px 12px rgba(107, 114, 128, 0.4);
                }
                
                .raw-data { 
                    background: #1F2937;
                    color: #E5E7EB;
                    padding: 25px;
                    border-radius: 12px;
                    overflow-x: auto;
                    max-height: 500px;
                    font-family: 'Monaco', 'Courier New', monospace;
                    font-size: 0.9em;
                    line-height: 1.6;
                    box-shadow: inset 0 2px 8px rgba(0, 0, 0, 0.3);
                }
                
                .metric-explanation {
                    background: #F9FAFB;
                    padding: 30px;
                    border-radius: 12px;
                    margin: 40px 0;
                    border-left: 4px solid #8B5CF6;
                    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
                    border: 1px solid #E5E7EB;
                }
                
                .metric-explanation h3 {
                    color: #4C1D95;
                    font-size: 1.4em;
                    margin-bottom: 20px;
                    font-weight: 700;
                }
                
                .metric-explanation .metric-item {
                    margin-bottom: 16px;
                    padding-left: 20px;
                    position: relative;
                }
                
                .metric-explanation .metric-item::before {
                    content: '▸';
                    position: absolute;
                    left: 0;
                    color: #8B5CF6;
                    font-weight: bold;
                }
                
                .metric-explanation strong { 
                    color: #4C1D95;
                    font-weight: 700;
                }
                
                @media (max-width: 768px) {
                    .header h1 { font-size: 1.8em; }
                    .content { padding: 20px; }
                    .metric-grid { grid-template-columns: 1fr; }
                    .controls { flex-direction: column; }
                    .btn { width: 100%; }
                }
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>📚 Physics Dataset Evaluation Report</h1>
                    <p>Comprehensive Analysis of Dataset Quality & Characteristics</p>
                </div>
                
                <div class="content">
                    <h2>📊 Global Dataset Metrics</h2>
                    
                    <div class="metric-grid">
                        <div class="card">
                            <h3>Total Problems</h3>
                            <p>""" + str(g_res['size']) + """</p>
                        </div>
                        <div class="card """ + ('success' if g_res['distinctness']['text_uniqueness_pct'] >= 90 else '') + """">
                            <h3>Text Uniqueness</h3>
                            <p>""" + str(g_res['distinctness']['text_uniqueness_pct']) + """%</p>
                        </div>
                        <div class="card """ + ('success' if g_res['distinctness']['signature_uniqueness_pct'] >= 90 else 'warning' if g_res['distinctness']['signature_uniqueness_pct'] >= 75 else '') + """">
                            <h3>Signature Uniqueness</h3>
                            <p>""" + str(g_res['distinctness']['signature_uniqueness_pct']) + """%</p>
                        </div>
                        <div class="card """ + ('alert' if g_res['distinctness']['duplicate_texts'] > g_res['size'] * 0.1 else 'warning' if g_res['distinctness']['duplicate_texts'] > 0 else 'success') + """">
                            <h3>Duplicate Texts</h3>
                            <p>""" + str(g_res['distinctness']['duplicate_texts']) + """</p>
                        </div>
                        <div class="card">
                            <h3>Avg Formulas/Problem</h3>
                            <p>""" + str(g_res['difficulty']['avg_formulas_per_prob']) + """</p>
                        </div>
                        <div class="card """ + ('success' if g_res['numerical_quality']['valid_results_pct'] == 100 else 'warning' if g_res['numerical_quality']['valid_results_pct'] >= 95 else 'alert') + """">
                            <h3>Valid Answers</h3>
                            <p>""" + str(g_res['numerical_quality']['valid_results_pct']) + """%</p>
                        </div>
                        <div class="card """ + ('alert' if g_res['numerical_quality']['unrealistic_values'] > g_res['size'] * 0.05 else 'warning' if g_res['numerical_quality']['unrealistic_values'] > 0 else 'success') + """">
                            <h3>Unrealistic Values</h3>
                            <p>""" + str(g_res['numerical_quality']['unrealistic_values']) + """</p>
                        </div>
                        <div class="card">
                            <h3>Avg Code Length</h3>
                            <p>""" + str(g_res['code_stats']['avg_char_length']) + """</p>
                        </div>
                        <div class="card """ + ('success' if g_res['generation_quality']['type_token_ratio'] >= 60 else 'warning' if g_res['generation_quality']['type_token_ratio'] >= 45 else '') + """">
                            <h3>Diversity (TTR)</h3>
                            <p>""" + str(g_res['generation_quality']['type_token_ratio']) + """%</p>
                        </div>
                        <div class="card">
                            <h3>Unique Formulas</h3>
                            <p>""" + str(g_res['content_balance']['unique_formulas_used']) + """</p>
                        </div>
                        <div class="card">
                            <h3>Unique Unknowns</h3>
                            <p>""" + str(g_res['content_balance']['unique_unknowns_used']) + """</p>
                        </div>
                        <div class="card">
                            <h3>Avg Word Count</h3>
                            <p>""" + str(g_res['generation_quality']['avg_word_count']) + """</p>
                        </div>
                    </div>

                    <h2>📈 Global Visualizations</h2>
                    <div class="plot-container">
                        <img src="data:image/png;base64,""" + plot_dict['global'] + """" alt="Global Evaluation Plots">
                    </div>

                    <h2>📑 Chapter-wise Details</h2>
                    <div class="controls">
                        <button class="btn" onclick="expandAll()">Expand All Chapters</button>
                        <button class="btn btn-secondary" onclick="collapseAll()">Collapse All Chapters</button>
                    </div>
                    <table>
                        <thead>
                            <tr>
                                <th>Chapter (click to expand)</th>
                                <th>Size</th>
                                <th>Difficulty</th>
                                <th>Avg Formulas</th>
                                <th>Text Unique %</th>
                                <th>Diversity (TTR)</th>
                            </tr>
                        </thead>
                        <tbody>
        """
        
        # Loop through chapters for rows and detail panels
        for chapter, metrics in sorted(self.results['chapters'].items()):
            chapter_id = self.sanitize_id(chapter)
            html += f"""
                        <tr class="clickable-row" onclick="toggleChapter('{chapter_id}')">
                            <td><strong>{chapter}</strong></td>
                            <td>{metrics['size']}</td>
                            <td>{metrics['difficulty']['level']}</td>
                            <td>{metrics['difficulty']['avg_formulas_per_prob']}</td>
                            <td>{metrics['distinctness']['text_uniqueness_pct']}%</td>
                            <td>{metrics['generation_quality']['type_token_ratio']}%</td>
                        </tr>
                        <tr>
                            <td colspan="6" style="padding: 0; border: none;">
                                <div id="detail_{chapter_id}" class="chapter-detail">
                                    <h3>📖 {chapter} - Detailed Metrics</h3>
                                    <div class="detail-grid">
                                        <div class="detail-card">
                                            <h4>Problems</h4>
                                            <p>{metrics['size']}</p>
                                        </div>
                                        <div class="detail-card">
                                            <h4>Valid Results</h4>
                                            <p>{metrics['numerical_quality']['valid_results_pct']}%</p>
                                        </div>
                                        <div class="detail-card">
                                            <h4>Unrealistic Values</h4>
                                            <p>{metrics['numerical_quality']['unrealistic_values']}</p>
                                        </div>
                                        <div class="detail-card">
                                            <h4>Duplicate Texts</h4>
                                            <p>{metrics['distinctness']['duplicate_texts']}</p>
                                        </div>
                                        <div class="detail-card">
                                            <h4>Sig Unique %</h4>
                                            <p>{metrics['distinctness']['signature_uniqueness_pct']}%</p>
                                        </div>
                                        <div class="detail-card">
                                            <h4>Avg Code Length</h4>
                                            <p>{metrics['code_stats']['avg_char_length']}</p>
                                        </div>
                                        <div class="detail-card">
                                            <h4>Unique Formulas</h4>
                                            <p>{metrics['content_balance']['unique_formulas_used']}</p>
                                        </div>
                                        <div class="detail-card">
                                            <h4>Unique Unknowns</h4>
                                            <p>{metrics['content_balance']['unique_unknowns_used']}</p>
                                        </div>
                                        <div class="detail-card">
                                            <h4>Avg Word Count</h4>
                                            <p>{metrics['generation_quality']['avg_word_count']}</p>
                                        </div>
                                    </div>
                                    <div class="plot-container">
                                        <img src="data:image/png;base64,{plot_dict['chapters'][chapter]}" alt="{chapter} plots">
                                    </div>
                                </div>
                            </td>
                        </tr>
            """

        html += """
                        </tbody>
                    </table>

                    <div class="metric-explanation">
                        <h3>📋 Metric Explanations</h3>
                        
                        <div class="metric-item">
                            <strong>Total Problems:</strong> Total number of physics problems in the dataset or chapter.
                        </div>
                        
                        <div class="metric-item">
                            <strong>Text Uniqueness:</strong> Percentage of problems with unique wording computed as <code>(unique_texts / total_texts) × 100</code>. Higher values indicate less repetition in problem statements.
                        </div>
                        
                        <div class="metric-item">
                            <strong>Signature Uniqueness:</strong> Percentage of distinct problem signatures computed as <code>(unique_signatures / total_signatures) × 100</code>, where each signature represents a unique combination of formulas and unknown variable. Higher values indicate more diverse problem structures.
                        </div>
                        
                        <div class="metric-item">
                            <strong>Duplicate Texts:</strong> Number of problems with non-unique wording, calculated as <code>total_texts - unique_texts</code>. Lower is better for dataset diversity.
                        </div>
                        
                        <div class="metric-item">
                            <strong>Avg Formulas/Problem:</strong> Mean number of physics formulas used per problem, computed as <code>mean(formula_counts_per_problem)</code>. Indicates problem complexity.
                        </div>
                        
                        <div class="metric-item">
                            <strong>Valid Answers:</strong> Percentage of problems with non-null numerical results, computed as <code>(problems_with_results / total_problems) × 100</code>. Should ideally be 100%.
                        </div>
                        
                        <div class="metric-item">
                            <strong>Unrealistic Values:</strong> Count of numerical results that are either extremely large <code>(|value| > 10¹⁵)</code> or extremely small <code>(|value| < 10⁻¹⁵)</code>, which may indicate computational errors or physically implausible scenarios.
                        </div>
                        
                        <div class="metric-item">
                            <strong>Avg Code Length:</strong> Mean character count of solution code snippets, computed as <code>mean(len(code))</code>. Provides insight into solution complexity.
                        </div>
                        
                        <div class="metric-item">
                            <strong>Diversity (Type-Token Ratio / TTR):</strong> Vocabulary richness measured as <code>(unique_words / total_words) × 100</code> across all problem texts. Higher values indicate more varied language and less repetitive wording.
                        </div>
                        
                        <div class="metric-item">
                            <strong>Unique Formulas:</strong> Total count of distinct formula identifiers used across all problems, computed as <code>len(set(all_formula_ids))</code>. Indicates breadth of physics concepts covered.
                        </div>
                        
                        <div class="metric-item">
                            <strong>Unique Unknowns:</strong> Total count of distinct unknown variables being solved for, computed as <code>len(set(all_unknown_vars))</code>. Shows variety in problem objectives.
                        </div>
                        
                        <div class="metric-item">
                            <strong>Avg Word Count:</strong> Mean number of words per problem statement, computed as <code>mean(word_counts)</code>. Indicates average problem description length.
                        </div>
                        
                        <div class="metric-item">
                            <strong>Difficulty Level:</strong> Categorical assessment based on average formulas per problem: <em>Easy</em> (< 2), <em>Medium</em> (2-3), or <em>Hard</em> (> 3).
                        </div>
                    </div>

                    <h2>🔧 Raw Global Data</h2>
                    <div class="plot-container">
                        <pre class="raw-data">""" + json.dumps(g_res, indent=2) + """</pre>
                    </div>
                </div>
            </div>
            
            <script>
                function toggleChapter(chapterId) {
                    const detail = document.getElementById('detail_' + chapterId);
                    detail.classList.toggle('active');
                }
                
                function expandAll() {
                    const details = document.querySelectorAll('.chapter-detail');
                    details.forEach(detail => detail.classList.add('active'));
                }
                
                function collapseAll() {
                    const details = document.querySelectorAll('.chapter-detail');
                    details.forEach(detail => detail.classList.remove('active'));
                }
            </script>
        </body>
        </html>
        """
        return html

# ========== MAIN EXECUTION ==========

if __name__ == "__main__":
    
    # # 1. SETUP: Create Dummy Data for Testing
    # # (Delete this block if you have real data)
    # dummy_folder = "chapterwise_generated_dataset"
    # if not os.path.exists(dummy_folder):
    #     os.makedirs(dummy_folder)
        
    # print("Generating dummy data for testing...")
    # # Chapter 1: Newton's Laws (Simulating duplicate signatures but unique text)
    # data_nlm = []
    # for i in range(25):
    #     data_nlm.append({
    #         "signature": f"F=ma|a_{i%5}", # Repeating signatures
    #         "formula_ids": ["F1", "F2"], 
    #         "unknown_var": "acceleration",
    #         "word_problem": f"A block of mass {i}kg is pushed with force...",
    #         "code": "a = F/m",
    #         "result": 10.0 + i
    #     })
    # with open(f"{dummy_folder}/5.NLM.json", 'w') as f: json.dump(data_nlm, f)

    # # Chapter 2: Rotation (Complex, High Formulas)
    # data_rot = []
    # for i in range(20):
    #     data_rot.append({
    #         "signature": f"rot_{i}", 
    #         "formula_ids": ["F5", "F6", "F7", "F8"], # 4 formulas -> Hard
    #         "unknown_var": "torque" if i % 2 == 0 else "inertia",
    #         "word_problem": f"A disk rotates with angular velocity {i}...",
    #         "code": "tau = I * alpha",
    #         "result": 50.5 + i
    #     })
    # with open(f"{dummy_folder}/9.Rotation.json", 'w') as f: json.dump(data_rot, f)
    
    # 2. RUN EVALUATOR
    # Replace 'dummy_folder' with your actual folder path
    evaluator = PhysicsDatasetEvaluator(data_folder_path="chapterwise_generated_dataset")
    
    # Calculate metrics
    results = evaluator.evaluate_all()
    
    # Generate the single HTML report
    if results:
        evaluator.generate_report(output_file='Physics_Evaluation_Report.html')