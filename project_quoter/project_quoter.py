from window_quoter.window_quoter import WindowQuoter
from valid_config_generator.valid_config_generator import ValidConfigGenerator
from typing import List, Dict, Tuple, Union
from collections import OrderedDict
import json
import os


class ProjectQuoter:
    def __init__(self, model_name: str, pricing_config_path: str = "valid_config_generator/pricing.conf", debug = False):
        self.pricing_config_path = pricing_config_path
        self.model_name = model_name
        self.debug = debug
    
    def format_window_description(self, window_data: Dict) -> str:
        """Format window data into a description string for config generation"""
        description = window_data['description']
        width = window_data['width']
        height = window_data['height']
        
        formatted_description = f"{description}, width: {width}, height: {height}"
        return formatted_description
        
    def cleanup_temp_files(self, num_windows: int) -> None:
        """Clean up temporary config files"""
        for i in range(1, num_windows + 1):
            temp_file = f"temp_window_{i}.conf"
            if os.path.exists(temp_file):
                try:
                    os.remove(temp_file)
                except:
                    pass  # Ignore cleanup errors
            
    def quote_project(self, window_descriptions: Dict) -> Tuple[float, Dict]:
        """Quote all windows in the project and return total cost and breakdown"""
        failed_configs = []
        
        # Initialize the config generator
        config_generator = ValidConfigGenerator(self.model_name)
        total_cost = 0.0
        project_breakdown = {}
        successful_window_num = 0

        # Process each window description with quantity
        for i, (window_key, window_data) in enumerate(window_descriptions.items(), 1):
            quantity = int(window_data['quantity'])
            
            # Format the window description with width and height
            formatted_description = self.format_window_description(window_data)
            
            config_file = f"temp_window_{i}.conf"
            print(f"\nProcessing window {i}: {formatted_description} (Quantity: {quantity})")
            
            # Generate and validate config
            if config_generator.generate_config(formatted_description, config_file):
                try:
                    # Create window quoter with generated config
                    window_cost, window_breakdown = WindowQuoter(config_file, self.pricing_config_path).quote_window()
                    if 'Error' in window_breakdown.keys():
                        print(f"✗ Failed to generate price breakdown for window {i}")
                        failed_configs.append((i, formatted_description, "Price breakdown generation failed"))
                    else:
                        window_key = f"Window {i}"
                        project_breakdown[window_key] = {
                            'cost': window_cost,
                            'breakdown': window_breakdown,
                            'quantity': quantity
                        }
                        # Add total cost for this window type (unit cost * quantity)
                        total_window_cost = window_cost * quantity
                        total_cost += total_window_cost
                        successful_window_num += 1
                        print(f"✓ Successfully created quote for window {i}")
                except Exception as e:
                    print(f"✗ Failed to create quote for window {i}: {e}")
                    failed_configs.append((i, formatted_description, str(e)))
            else:
                print(f"✗ Failed to generate valid config for window {i}")
                failed_configs.append((i, formatted_description, "Config generation failed"))
        
        

        # Add failed configs info
        if failed_configs:
            project_breakdown['Failed Windows'] = {
                'count': len(failed_configs),
                'details': [f"Window {i}: {desc[:50]}... - {error}" for i, desc, error in failed_configs]
            }
            
        project_breakdown['Total Project Cost'] = total_cost
        project_breakdown['Quoted Windows'] = len(window_descriptions)
        
        # Clean up temp files
        if self.debug == False:
            self.cleanup_temp_files(len(window_descriptions))
        
        return total_cost, self.format_json(project_breakdown)
    
    def format_json(self, project_breakdown: Dict) -> OrderedDict:
        """Format project breakdown with ordered keys, starting with 'Quoted Windows'"""
        formatted = OrderedDict()
        
        # Add 'Quoted Windows' first
        if 'Quoted Windows' in project_breakdown:
            formatted['Quoted Windows'] = project_breakdown['Quoted Windows']
        
        # Add window details in order with nested structure
        window_keys = sorted([k for k in project_breakdown.keys() if k.startswith('Window ')], 
                           key=lambda x: int(x.split()[1]))
        for window_key in window_keys:
            window_data = project_breakdown[window_key]
            formatted_window = OrderedDict()
            
            # Add quantity first, then sf, lf
            quantity = window_data.get('quantity', 1)
            formatted_window['Quantity'] = quantity
            
            breakdown = window_data['breakdown']
            formatted_window['Square Feet'] = f"{breakdown['sf']:.2f}"
            formatted_window['Linear Feet'] = f"{breakdown['lf']:.2f}"
            
            formatted_breakdown = OrderedDict()
            base_price_key = [k for k in breakdown.keys() if 'Base Price' in k]
            formatted_breakdown[base_price_key[0]] = f"${breakdown[base_price_key[0]]:.2f}"
            glass_price_key = [k for k in breakdown.keys() if 'Glass Base Price' in k]
            formatted_breakdown[glass_price_key[0]] = f"${breakdown[glass_price_key[0]]:.2f}"

            # Add any other breakdown items with $ formatting
            for key in breakdown:
                if key not in ['sf', 'lf', base_price_key[0], glass_price_key[0]] and key not in formatted_breakdown:
                    value = breakdown[key]
                    if isinstance(value, (int, float)):
                        formatted_breakdown[key] = f"${value:.2f}"
                    else:
                        formatted_breakdown[key] = value
            
            formatted_window['Cost Breakdown'] = formatted_breakdown
            
            formatted_window['Window Cost (Single)'] = f"${window_data['cost']:.2f}"
            
            # Add Total (Quantity: N) line if quantity > 1
            quantity = window_data.get('quantity', 1)
            if quantity > 1:
                total_cost = window_data['cost'] * quantity
                formatted_window[f'Window Cost (Quantity: {quantity})'] = f"${total_cost:.2f}"
            
            formatted[window_key] = formatted_window
            print("formatted", formatted)

        
        # Add Failed Windows if it exists
        if 'Failed Windows' in project_breakdown:
            formatted['Failed Windows'] = project_breakdown['Failed Windows']
        
        # Add Total Project Cost at the bottom with $ formatting
        if 'Total Project Cost' in project_breakdown:
            total_cost_value = project_breakdown['Total Project Cost']
            if isinstance(total_cost_value, str) and total_cost_value.startswith('$'):
                formatted['Total Project Cost'] = total_cost_value
            elif isinstance(total_cost_value, (int, float)):
                formatted['Total Project Cost'] = f"${total_cost_value:.2f}"
            else:
                formatted['Total Project Cost'] = total_cost_value
        
        return formatted
        

        