from window_quoter.helper_funcs import *
from pyhocon import ConfigFactory

class WindowQuoter:
    def __init__(self, window_config_path, pricing_config_path):
        self.window_config = ConfigFactory.parse_file(f"{window_config_path}")
        self.pricing_config = ConfigFactory.parse_file(f"{pricing_config_path}")
        self.width = self.window_config.get('width')
        self.height = self.window_config.get('height')
        self.sf = calculate_sf(self.width, self.height)
        self.lf = calculate_lf(self.width, self.height)
        self.window_type = self.window_config.get('window_type')
        self.interior_finish = getOrReturnNone(self.window_config, f"{self.window_type}.interior") if self.window_type in ['casement', 'awning', 'picture_window','fixed_casement'] else 'white'
        self.exterior_finish = getOrReturnNone(self.window_config, f"{self.window_type}.exterior")
        self.hardware_config = getOrReturnNone(self.window_config, f"{self.window_type}.hardware")
        self.shape_config = getOrReturnNone(self.window_config, "shapes")
        if self.shape_config is not None and getOrReturnNone(self.shape_config, "type") is None:
            self.shape_config = None
        self.glass_config = getOrReturnNone(self.window_config, "glass")
        self.brickmould_config = getOrReturnNone(self.window_config, "brickmould")
        if self.brickmould_config is not None and not getOrReturnNone(self.brickmould_config, "include"):
            self.brickmould_config = None
        self.casing_extension_config = getOrReturnNone(self.window_config, "casing_extension")
        if self.casing_extension_config is not None and not getOrReturnNone(self.casing_extension_config, "type"):
            self.casing_extension_config = None

    def quote_frame(self, price_breakdown = {}, current_price = 0.0):

        # 1. Basic Calculations
        if self.sf <= 0: # Basic validation
            price_breakdown['Error'] = "Width and Height must be greater than 0."
            return 0, price_breakdown
        price_breakdown['sf'] = self.sf
        price_breakdown['lf'] = self.lf
        
        # 2. Base Price - use white pricing for stain, actual finish for others
        try:
            base_finish = 'white' if self.interior_finish == 'stain' else self.interior_finish
            base_p = get_base_price(self.window_type, base_finish, self.pricing_config, self.sf)
            price_breakdown[f'Base Price ({self.window_type} interior {base_finish})'] = base_p
            current_price += base_p
        except ValueError as e:
            price_breakdown['Error'] = f"Base Price Error: {e}"
            return 0, price_breakdown

        # 3. Exterior Finish Upcharge
        if self.exterior_finish is not None and self.exterior_finish != 'white':
            if self.exterior_finish == 'color':
                exterior_upcharge = base_p * getOrReturnNone(self.pricing_config, f"{self.window_type}.exterior.color_base_perc")
                price_breakdown['Exterior Color Upcharge'] = exterior_upcharge
                current_price += exterior_upcharge
            elif self.exterior_finish == 'custom_color':
                exterior_upcharge = base_p * getOrReturnNone(self.pricing_config, f"{self.window_type}.exterior.color_base_perc")
                custom_color_add_on = getOrReturnNone(self.pricing_config, f"{self.window_type}.exterior.custom_color_add_on")
                exterior_upcharge += custom_color_add_on
                price_breakdown['Exterior Custom Color Upcharge'] = exterior_upcharge
                current_price += exterior_upcharge
            elif self.exterior_finish == 'stain':
                stain_cost = getOrReturnNone(self.pricing_config, f"{self.window_type}.exterior.stain_add_on")
                if stain_cost is not None:
                    price_breakdown['Exterior Stain Add-on'] = stain_cost
                    current_price += stain_cost
            
        # 4. Interior Stain Upcharge
        if self.interior_finish == 'stain':
            stain_cost = getOrReturnNone(self.pricing_config, f"{self.window_type}.interior.stain_add_on")
            if stain_cost is not None:
                price_breakdown['Interior Stain Add-on'] = stain_cost
                current_price += stain_cost

        # 5. Hardware Options
        if self.hardware_config:
            for hardware, incl_bool in self.hardware_config.items():
                if incl_bool:
                    cost = getOrReturnNone(self.pricing_config, f"{self.window_type}.{hardware}")
                    if cost is not None:
                        price_breakdown[f"Hardware: {hardware}"] = cost
                        current_price += cost

        # 6. Shape Add-on
        if self.shape_config is not None:
            shape_type = getOrReturnNone(self.shape_config, "type")
            shape_cost = getOrReturnNone(self.pricing_config, f"shapes.{shape_type}")
            price_breakdown[f"Shape Add-on: {shape_type}"] = shape_cost
            current_price += shape_cost
            extras = getOrReturnNone(self.shape_config, "extras")
            if extras:
                for extra, incl_bool in extras.items():
                    if incl_bool:
                        cost = getOrReturnNone(self.pricing_config, f"shapes.{extra}")
                        price_breakdown[f"Shape Add-on Extra: {extra}"] = cost
                        current_price += cost

        return current_price, price_breakdown

    def quote_glass(self, price_breakdown = {}, current_price = 0.0):
        glass_type = getOrReturnNone(self.glass_config, 'type')
        glass_subtype = getOrReturnNone(self.glass_config, 'subtype')
        glass_thickness = getOrReturnNone(self.glass_config, 'thickness_mm')
        min_sf = getOrReturnNone(self.pricing_config, f"glass.{glass_type}.min_size_sf")
        
        # Get the glass price brackets for the specific subtype
        glass_price_brackets = getOrReturnNone(self.pricing_config, f"glass.{glass_type}.{glass_subtype}")
        if glass_price_brackets is None:
            price_breakdown['Error'] = f"Glass pricing not found for {glass_type}.{glass_subtype}"
            return 0, price_breakdown
            
        # Find the matching thickness bracket
        glass_price_unit = None
        for bracket in glass_price_brackets:
            if getOrReturnNone(bracket, 'thickness') == glass_thickness:
                glass_price_unit = getOrReturnNone(bracket, 'price')
                break
                
        if glass_price_unit is None:
            price_breakdown['Error'] = f"Glass price not found for thickness {glass_thickness}mm"
            return 0, price_breakdown
            


        # Calculate base glass price
        glass_price = glass_price_unit * min(self.sf, min_sf)
        current_price += glass_price
        price_breakdown[f"Glass Base Price ({glass_type} {glass_subtype} {glass_thickness}mm)"] = glass_price
        
        # Add shape surcharge if applicable
        if self.shape_config is not None:
            shape_add_on = getOrReturnNone(self.pricing_config, f"glass.{glass_type}.shaped_add_on")
            current_price += shape_add_on
            price_breakdown[f"Glass Shape Add-on"] = shape_add_on
            
        return current_price, price_breakdown

    def quote_trim(self, price_breakdown = {}, current_price = 0.0):
        if self.brickmould_config:
            brickmould_cost = self.lf * getOrReturnNone(self.pricing_config, f"brickmould.{getOrReturnNone(self.brickmould_config, 'size')}.{getOrReturnNone(self.brickmould_config, 'finish')}")
            price_breakdown[f"Brickmould ({getOrReturnNone(self.brickmould_config, 'size')}, {getOrReturnNone(self.brickmould_config, 'finish')})"] = brickmould_cost
            current_price += brickmould_cost

        if self.casing_extension_config:
            if getOrReturnNone(self.casing_extension_config, 'type') == 'wood_ext':
                # Get wood extension price brackets
                wood_ext_brackets = getOrReturnNone(self.pricing_config, "casing_extension.wood_ext")
                if wood_ext_brackets is None:
                    price_breakdown['Error'] = "Wood extension pricing not found"
                    return 0, price_breakdown
                    
                # Convert brackets to format expected by calculate_price_from_brackets
                converted_brackets = []
                for bracket in wood_ext_brackets:
                    max_size = getOrReturnNone(bracket, 'max_size')
                    price = getOrReturnNone(bracket, 'price')
                    over_rate = getOrReturnNone(bracket, 'over_rate', 0)
                    converted_brackets.append((max_size, price, over_rate))
                    
                casing_extension_cost = calculate_price_from_brackets(self.lf, converted_brackets, "Wood extension")
            else:
                casing_extension_cost = self.lf * getOrReturnNone(self.pricing_config, f"casing_extension.{getOrReturnNone(self.casing_extension_config, 'type')}.{getOrReturnNone(self.casing_extension_config, 'finish')}")
            price_breakdown[f"Casing Extension ({getOrReturnNone(self.casing_extension_config, 'type')}, {getOrReturnNone(self.casing_extension_config, 'finish')})"] = casing_extension_cost
            current_price += casing_extension_cost

            if getOrReturnNone(self.casing_extension_config, "include_bay_bow_extension"):
                bay_bow_extension_cost = getOrReturnNone(self.pricing_config, "casing_extension.bay_bow_extension")
                price_breakdown[f"Bay & Bow Extension"] = bay_bow_extension_cost
                current_price += bay_bow_extension_cost

            if getOrReturnNone(self.casing_extension_config, "include_bay_bow_plywood"):
                # Get bay/bow plywood price brackets
                plywood_brackets = getOrReturnNone(self.pricing_config, "casing_extension.bay_bow_plywood")
                if plywood_brackets is None:
                    price_breakdown['Error'] = "Bay/bow plywood pricing not found"
                    return 0, price_breakdown
                    
                # Convert brackets to format expected by calculate_price_from_brackets
                converted_brackets = []
                for bracket in plywood_brackets:
                    max_size = getOrReturnNone(bracket, 'max_size')
                    price = getOrReturnNone(bracket, 'price')
                    over_rate = getOrReturnNone(bracket, 'over_rate', 0)
                    converted_brackets.append((max_size, price, over_rate))
                    
                bay_bow_plywood_cost = calculate_price_from_brackets(self.lf, converted_brackets, "Bay/bow plywood")
                price_breakdown[f"Bay & Bow Plywood"] = bay_bow_plywood_cost
                current_price += bay_bow_plywood_cost

        return current_price, price_breakdown


    def quote_window(self):
        current_price = 0
        price_breakdown = {}

        current_price, price_breakdown = self.quote_frame(price_breakdown, current_price)
        current_price, price_breakdown = self.quote_glass(price_breakdown, current_price)
        current_price, price_breakdown = self.quote_trim(price_breakdown, current_price)

        return round(current_price, 2), price_breakdown

"""
                ## TODO: implement grills, sdl
        # 8. Grills
        grill_cost = 0
        grill_type_sel = config.get('grill_type', 'None')
        if grill_type_sel != 'None':
            num_squares = config.get('grill_squares', 0)
            price_per_sq = grill_prices_per_sq.get(grill_type_sel)
            if price_per_sq is not None and num_squares > 0:
                grill_cost = price_per_sq * num_squares
                price_breakdown[f"Grills: {grill_type_sel} ({num_squares} squares @ {price_per_sq:.2f}/sq)"] = f"{grill_cost:.2f}"
                current_price += grill_cost
            elif num_squares <= 0:
                st.warning(f"Number of squares must be > 0 for grills.")
            else:
                st.warning(f"Grill type '{grill_type_sel}' not found.")

        # 9. SDL
        sdl_cost = 0
        sdl_type_sel = config.get('sdl_type', 'None')
        if sdl_type_sel != 'None':
            num_squares = config.get('sdl_squares', 0)
            price_per_sq = sdl_prices_per_sq.get(sdl_type_sel)
            if price_per_sq is not None and num_squares > 0:
                sdl_cost = price_per_sq * num_squares
                price_breakdown[f"SDL: {sdl_type_sel} ({num_squares} squares @ {price_per_sq:.2f}/sq)"] = f"{sdl_cost:.2f}"
                current_price += sdl_cost
            elif num_squares <= 0:
                st.warning(f"Number of squares must be > 0 for SDL.")
            else:
                st.warning(f"SDL type '{sdl_type_sel}' not found.")
"""