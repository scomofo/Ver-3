from datetime import datetime

class QuoteBuilder:
    """Helper class for building quote data structures."""
    
    @staticmethod
    def create_basic_quote(dealer_racf_id, customer_data, quote_name, expiration_date=None):
        """Create a basic quote structure.
        
        Args:
            dealer_racf_id: Dealer RACF ID
            customer_data: Customer information
            quote_name: Name for the quote
            expiration_date: Expiration date (optional)
            
        Returns:
            Basic quote data structure
        """
        # Validate required fields
        if not dealer_racf_id or not customer_data or not quote_name:
            raise ValueError("Missing required fields for quote")
        
        # Basic quote structure
        quote = {
            "dealerRacfId": dealer_racf_id,
            "quoteName": quote_name,
            "customerData": customer_data,
            "quoteStatusId": 1,  # Default status (active)
            "quoteType": 2,      # Default type
            "equipmentData": []
        }
        
        # Add optional fields
        if expiration_date:
            quote["expirationDate"] = expiration_date
        
        # Add current creation date
        quote["creationDate"] = datetime.now().strftime("%m/%d/%Y")
        
        return quote
    
    @staticmethod
    def create_customer_data(first_name, last_name, email=None, phone=None, address=None, city=None, state=None, zip_code=None, country="US"):
        """Create customer data structure.
        
        Args:
            first_name: Customer first name
            last_name: Customer last name
            email: Customer email (optional)
            phone: Customer phone (optional)
            address: Customer address (optional)
            city: Customer city (optional)
            state: Customer state (optional)
            zip_code: Customer ZIP code (optional)
            country: Customer country (default: US)
            
        Returns:
            Customer data structure
        """
        # Basic customer data
        customer = {
            "customerFirstName": first_name,
            "customerLastName": last_name,
            "customerCountry": country
        }
        
        # Add optional fields
        if email:
            customer["customerEmail"] = email
        if phone:
            customer["customerPhone"] = phone
        if address:
            customer["customerAddr1"] = address
        if city:
            customer["customerCity"] = city
        if state:
            customer["customerState"] = state
        if zip_code:
            customer["customerZipCode"] = zip_code
        
        return customer
    
    @staticmethod
    def create_equipment_data(make_id, model_id, category_id, dealer_specified_model, list_price, cost_price=None, year_of_manufacture=None, serial_no=None, dealer_stock_number=None):
        """Create equipment data structure.
        
        Args:
            make_id: Equipment make ID
            model_id: Equipment model ID
            category_id: Equipment category ID
            dealer_specified_model: Model name
            list_price: List price
            cost_price: Cost price (optional)
            year_of_manufacture: Manufacturing year (optional)
            serial_no: Serial number (optional)
            dealer_stock_number: Dealer stock number (optional)
            
        Returns:
            Equipment data structure
        """
        # Basic equipment data
        equipment = {
            "makeID": make_id,
            "modelID": model_id,
            "categoryID": category_id,
            "dealerSpecifiedModel": dealer_specified_model,
            "listPrice": list_price,
            "includeInRecapProposal": True
        }
        
        # Add optional fields
        if cost_price:
            equipment["costPrice"] = cost_price
        if year_of_manufacture:
            equipment["yearOfManufacture"] = year_of_manufacture
        if serial_no:
            equipment["serialNo"] = serial_no
        if dealer_stock_number:
            equipment["dealerStockNumber"] = dealer_stock_number
        
        # Initialize empty arrays
        equipment["equipmentOptionData"] = []
        equipment["attachmentData"] = []
        equipment["adjustmentData"] = []
        
        return equipment
    
    @staticmethod
    def add_option_to_equipment(equipment, option_code, option_desc, option_price_amount, option_cost_amount=None, option_type=0):
        """Add an option to equipment data.
        
        Args:
            equipment: Equipment data structure
            option_code: Option code
            option_desc: Option description
            option_price_amount: Option price
            option_cost_amount: Option cost (optional)
            option_type: Option type (default: 0)
            
        Returns:
            Updated equipment data
        """
        # Create option data
        option = {
            "optionCode": option_code,
            "optionDesc": option_desc,
            "optionPriceAmount": option_price_amount,
            "optionType": option_type
        }
        
        # Add optional fields
        if option_cost_amount:
            option["optionCostAmount"] = option_cost_amount
        
        # Add to equipment
        if "equipmentOptionData" not in equipment:
            equipment["equipmentOptionData"] = []
        
        equipment["equipmentOptionData"].append(option)
        
        return equipment
    
    @staticmethod
    def add_attachment_to_equipment(equipment, attachment_description, attachment_code, list_price, cost_price=None, attachment_type=0):
        """Add an attachment to equipment data.
        
        Args:
            equipment: Equipment data structure
            attachment_description: Attachment description
            attachment_code: Attachment code
            list_price: List price
            cost_price: Cost price (optional)
            attachment_type: Attachment type (default: 0)
            
        Returns:
            Updated equipment data
        """
        # Create attachment data
        attachment = {
            "attachmentDescription": attachment_description,
            "attachmentCode": attachment_code,
            "listPrice": list_price,
            "attachmentType": attachment_type
        }
        
        # Add optional fields
        if cost_price:
            attachment["costPrice"] = cost_price
        
        # Add to equipment
        if "attachmentData" not in equipment:
            equipment["attachmentData"] = []
        
        equipment["attachmentData"].append(attachment)
        
        return equipment
    
    @staticmethod
    def add_adjustment_to_equipment(equipment, description, list_price, cost_price=None):
        """Add an adjustment to equipment data.
        
        Args:
            equipment: Equipment data structure
            description: Adjustment description
            list_price: List price adjustment
            cost_price: Cost price adjustment (optional)
            
        Returns:
            Updated equipment data
        """
        # Create adjustment data
        adjustment = {
            "description": description,
            "listPrice": list_price
        }
        
        # Add optional fields
        if cost_price:
            adjustment["costPrice"] = cost_price
        
        # Add to equipment
        if "adjustmentData" not in equipment:
            equipment["adjustmentData"] = []
        
        equipment["adjustmentData"].append(adjustment)
        
        return equipment
    
    @staticmethod
    def add_trade_in_to_quote(quote, description, make_id, model_id, category_id, net_trade_value, year_of_manufacture=None, serial_no=None, hour_meter_reading=None, trade_tax_amount=None):
        """Add a trade-in to a quote.
        
        Args:
            quote: Quote data structure
            description: Trade-in description
            make_id: Make ID
            model_id: Model ID
            category_id: Category ID
            net_trade_value: Net trade value
            year_of_manufacture: Manufacturing year (optional)
            serial_no: Serial number (optional)
            hour_meter_reading: Hour meter reading (optional)
            trade_tax_amount: Trade tax amount (optional)
            
        Returns:
            Updated quote data
        """
        # Create trade-in data
        trade_in = {
            "description": description,
            "makeID": make_id,
            "modelID": model_id,
            "categoryID": category_id,
            "netTradeValue": net_trade_value,
            "includeInRecapProposal": True
        }
        
        # Add optional fields
        if year_of_manufacture:
            trade_in["yearOfManufacture"] = year_of_manufacture
        if serial_no:
            trade_in["serialNo"] = serial_no
        if hour_meter_reading:
            trade_in["hourMeterReading"] = hour_meter_reading
        if trade_tax_amount:
            trade_in["tradeTaxAmount"] = trade_tax_amount
        
        # Add to quote
        if "tradeInEquipmentData" not in quote:
            quote["tradeInEquipmentData"] = []
        
        quote["tradeInEquipmentData"].append(trade_in)
        
        # Update total net trade value
        if "totalNetTradeValue" not in quote:
            quote["totalNetTradeValue"] = 0
        
        quote["totalNetTradeValue"] += net_trade_value
        
        return quote
    
    @staticmethod
    def add_equipment_to_quote(quote, equipment):
        """Add equipment to a quote.
        
        Args:
            quote: Quote data structure
            equipment: Equipment data structure
            
        Returns:
            Updated quote data
        """
        # Add to quote
        if "equipmentData" not in quote:
            quote["equipmentData"] = []
        
        quote["equipmentData"].append(equipment)
        
        return quote