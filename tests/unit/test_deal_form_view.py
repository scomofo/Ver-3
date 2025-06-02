import unittest
from unittest.mock import patch, MagicMock, call
import urllib.parse

# It might be necessary to add the project root to sys.path if imports fail
# import sys
# import os
# sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..'))) 
# Adjust path as needed based on where the test runner executes from.

from views.modules.deal_form_view import DealFormView 

# Mocking PyQt classes that are instantiated or used directly if not easily mockable otherwise
class MockQLineEdit:
    def __init__(self, text=""):
        self._text = text
    def text(self): return self._text
    def setText(self, text): self._text = text
    def clear(self): self._text = ""
    def setFocus(self): pass
    def setPlaceholderText(self, text): pass
    def setCompleter(self, completer): pass # Add methods used by DealFormView
    def editingFinished(self): return MagicMock() # if connect is used

class MockQListWidget:
    def __init__(self):
        self.items = []
    def count(self): return len(self.items)
    def item(self, i): return self.items[i] if 0 <= i < len(self.items) else None
    def addItem(self, qlistwidgetitem_or_text): # DealFormView uses QListWidgetItem(text, list)
        if isinstance(qlistwidgetitem_or_text, str):
             # In real Qt, QListWidgetItem is an object. For testing, storing text is simpler.
            self.items.append(MagicMock(text=lambda: qlistwidgetitem_or_text)) # Mock item has a text() method
        else: # If a mock QListWidgetItem is passed
            self.items.append(qlistwidgetitem_or_text) 
    def clear(self): self.items = []


class MockQCheckBox:
    def __init__(self, checked=False):
        self._checked = checked
    def isChecked(self): return self._checked
    def setChecked(self, checked): self._checked = checked

class MockQTextEdit:
    def __init__(self, text=""):
        self._text = text
    def toPlainText(self): return self._text
    def setPlainText(self, text): self._text = text
    def clear(self): self._text = ""

class MockQMessageBox: # Static methods
    @staticmethod
    def warning(parent, title, message): pass
    # Add other static methods like information, critical if used by generate_email path

# Mock QListWidgetItem if its methods are accessed beyond .text()
class MockQListWidgetItem:
    def __init__(self, text=""):
        self._text = text
    def text(self):
        return self._text


class TestDealFormViewEmail(unittest.TestCase):

    @patch('views.modules.deal_form_view.QMessageBox', new=MockQMessageBox) # Patch static QMessageBox
    @patch('webbrowser.open', new_callable=MagicMock) # Mock webbrowser.open
    def setUp(self, mock_webbrowser_open): # mock_webbrowser_open is injected by @patch
        self.mock_webbrowser_open = mock_webbrowser_open # Store for assertions

        # Create an instance of DealFormView
        # Mock all dependencies DealFormView expects in its __init__
        mock_config = {} 
        mock_sharepoint_manager = MagicMock()
        mock_logger = MagicMock()
        
        # To allow DealFormView to be instantiated, we need to ensure all UI elements
        # it tries to create in init_ui are either replaced by mocks or their creation is patched.
        # The simplest way if init_ui is complex is to patch attributes after instantiation
        # or provide a mock that prevents init_ui from running its course.
        # For this test, we'll focus on mocking the attributes generate_email directly uses.

        with patch.object(DealFormView, 'init_ui', MagicMock(return_value=None)): # Skip UI init
            with patch.object(DealFormView, 'load_initial_data', MagicMock(return_value=None)): # Skip data loading
                 self.view = DealFormView(config=mock_config, 
                                         sharepoint_manager=mock_sharepoint_manager, 
                                         logger_instance=mock_logger)

        # Replace actual UI elements with mocks
        self.view.customer_name = MockQLineEdit()
        self.view.salesperson = MockQLineEdit()
        self.view.equipment_list = MockQListWidget()
        self.view.part_list = MockQListWidget()
        self.view.work_order_charge_to = MockQLineEdit()
        self.view.work_order_hours = MockQLineEdit()
        self.view.logger = mock_logger # Already passed but good to be explicit
        self.view._show_status_message = MagicMock() # Mock this internal method

        # Mock the helper parsing methods initially to ensure they are called,
        # then you can test their actual output by letting them run if they are simple enough
        # or by pre-populating their return values.
        # For this test, we'll rely on their actual implementation as provided in the prompt.
        # So, no need to patch _parse_equipment_item_for_email and _parse_part_item_for_email

    def tearDown(self):
        self.mock_webbrowser_open.reset_mock()

    def _assert_url_opened_with_params(self, expected_to, expected_cc, expected_subject_contains, expected_body_contains_lines):
        self.mock_webbrowser_open.assert_called_once()
        args, _ = self.mock_webbrowser_open.call_args
        actual_url = args[0]

        self.assertTrue(actual_url.startswith("https://outlook.office.com/mail/deeplink/compose"))
        
        parsed_url = urllib.parse.urlparse(actual_url)
        query_params = urllib.parse.parse_qs(parsed_url.query)

        self.assertEqual(query_params.get('to', [''])[0], expected_to)
        if expected_cc:
            self.assertEqual(query_params.get('cc', [''])[0], expected_cc)
        else:
            self.assertNotIn('cc', query_params)
        
        actual_subject = query_params.get('subject', [''])[0]
        for sub_text in expected_subject_contains:
            self.assertIn(sub_text, actual_subject)

        actual_body_url_encoded = query_params.get('body', [''])[0]
        actual_body = urllib.parse.unquote(actual_body_url_encoded) # Unquote the body from URL
        
        # Check for CRLF line endings in the source body before it's URL encoded
        # The prompt specified `body = "\r\n".join(body_lines)`
        # So, we check for 
 in the unquoted body.
        # Note: urllib.parse.unquote might convert %0D%0A to 
 depending on platform/version.
        # For robustness, check for both 
 and 
 if direct 
 check fails.
        
        # First, let's normalize line endings in actual_body to 
 for consistent comparison
        actual_body_normalized = actual_body.replace('\r\n', '\n').replace('\r', '\n')

        for line in expected_body_contains_lines:
            self.assertIn(line, actual_body_normalized)


    def test_email_with_equipment_and_parts(self):
        self.view.customer_name.setText("Test Customer Inc.")
        self.view.salesperson.setText("John Doe")
        self.view.equipment_list.addItem('"Test Mower XL" STK#TMXL001 $1200.50')
        self.view.equipment_list.addItem('"Mini Sprinkler" STK#MS002 $50.25')
        self.view.part_list.addItem('2x PN123 - Super Filter | Loc: Camrose | Charge to: WO-CUST')
        self.view.part_list.addItem('1x BOLT007 - Special Bolt') # No loc, no charge to
        self.view.work_order_hours.setText("3.5")
        self.view.work_order_charge_to.setText("WO-CUST") # Explicit WO charge to

        self.assertTrue(self.view.generate_email())

        expected_subject = ["AMS DEAL - Test Customer Inc.", "Test Mower XL"]
        expected_body = [
            "Customer: Test Customer Inc.",
            "Sales: John Doe",
            "EQUIPMENT",
            "--------------------------------------------------",
            "Test Mower XL STK# TMXL001 $1,200.50", # Check formatting
            "Mini Sprinkler STK# MS002 $50.25",
            "PARTS",
            "2 x Super Filter Camrose Charge to WO-CUST", # PN123 is part of name if parser puts it there
            "1 x Special Bolt Charge to WO-CUST", # Defaults to WO Charge to
            "WORK ORDER",
            "3.5 x Hours, charge to WO-CUST",
            "CDK and spreadsheet have been updated. John Doe to collect."
        ]
        self._assert_url_opened_with_params(
            "amsdeals@briltd.com", 
            "amsparts@briltd.com",
            expected_subject,
            expected_body
        )
        self.view.logger.info.assert_any_call("Generated Outlook deeplink. To: amsdeals@briltd.com, CC: amsparts@briltd.com, Subject: AMS DEAL - Test Customer Inc. (Test Mower XL)")

    def test_email_equipment_only_no_wo_charge_to(self):
        self.view.customer_name.setText("Equipment Only Ltd.")
        self.view.salesperson.setText("Jane Smith")
        self.view.equipment_list.addItem('"Generator G500" (Code: G5) STK#G500-01 $7500.00')
        # No parts
        self.view.work_order_hours.setText("1.0") # WO hours, but no explicit WO charge to

        self.assertTrue(self.view.generate_email())
        
        # effective_charge_to should be STK# of first equipment
        expected_charge_to = "STK# G500-01"

        expected_subject = ["AMS DEAL - Equipment Only Ltd.", "Generator G500"]
        expected_body = [
            "Customer: Equipment Only Ltd.",
            "Sales: Jane Smith",
            "EQUIPMENT",
            "Generator G500 STK# G500-01 $7,500.00",
            "WORK ORDER",
            f"1.0 x Hours, charge to {expected_charge_to}",
            "CDK and spreadsheet have been updated. Jane Smith to collect."
        ]
        self._assert_url_opened_with_params(
            "amsdeals@briltd.com",
            None, # No CC
            expected_subject,
            expected_body
        )
        self.assertNotIn("PARTS\n--------------------------------------------------", self.mock_webbrowser_open.call_args[0][0]) # Ensure PARTS section is not in URL

    def test_email_parts_only_charge_to_customer(self):
        self.view.customer_name.setText("Parts R Us")
        self.view.salesperson.setText("Mike Parts")
        # No Equipment
        self.view.part_list.addItem('5x FIL001 - Oil Filter | Loc: Killam')
        # No WO hours, no explicit WO charge to. Effective charge to should be customer name.
        
        self.assertTrue(self.view.generate_email())

        expected_charge_to = "Parts R Us" # Customer name

        expected_subject = ["AMS DEAL - Parts R Us", "Oil Filter"] # Assuming part name is used if no equipment
        expected_body = [
            "Customer: Parts R Us",
            "Sales: Mike Parts",
            "PARTS",
            f"5 x Oil Filter Killam Charge to {expected_charge_to}",
            "CDK and spreadsheet have been updated. Mike Parts to collect."
        ]
        self._assert_url_opened_with_params(
            "amsdeals@briltd.com",
            "amsparts@briltd.com", # CC because parts are present
            expected_subject,
            expected_body
        )
        self.assertNotIn("EQUIPMENT\n--------------------------------------------------", self.mock_webbrowser_open.call_args[0][0])
        self.assertNotIn("WORK ORDER\n--------------------------------------------------", self.mock_webbrowser_open.call_args[0][0])


    def test_email_missing_customer_name(self):
        # self.view.customer_name.setText("") # Already empty by default
        self.view.salesperson.setText("Sales Person")
        self.assertFalse(self.view.generate_email())
        self.mock_webbrowser_open.assert_not_called()
        # Test that QMessageBox.warning was called (via our mock)
        # This requires QMessageBox to be patched on the class or module level for generate_email to see it.
        # If QMessageBox is imported as `from PyQt6.QtWidgets import QMessageBox` in deal_form_view.py,
        # then it should be patched as `patch('views.modules.deal_form_view.QMessageBox', new=MockQMessageBox)`
        # which is done at the class level. So, this test should work.
        # The assertion of QMessageBox.warning call would be:
        # self.assertEqual(QMessageBox.warning.call_count, 1) -- if it's a mock object.
        # However, MockQMessageBox is a class with static methods, so we can't easily track calls this way
        # without making it more complex. For now, not calling webbrowser is the main check.
        self.view._show_status_message.assert_called_with("Email generation failed: Customer name missing.", 3000)


    def test_email_empty_deal_first_item_subject(self):
        self.view.customer_name.setText("Empty Deal Co.")
        self.view.salesperson.setText("Nobody")
        # No equipment, no parts
        
        self.assertTrue(self.view.generate_email())
        
        expected_subject = ["AMS DEAL - Empty Deal Co."] # No parenthetical part
        expected_body = [
            "Customer: Empty Deal Co.",
            "Sales: Nobody",
            "CDK and spreadsheet have been updated. Nobody to collect."
        ]
        
        # Check that the subject does NOT contain "()" or "( )"
        actual_url = self.mock_webbrowser_open.call_args[0][0]
        parsed_url = urllib.parse.urlparse(actual_url)
        query_params = urllib.parse.parse_qs(parsed_url.query)
        actual_subject = query_params.get('subject', [''])[0]
        self.assertNotIn("()", actual_subject)
        self.assertNotIn("( )", actual_subject) # Check for empty parentheses too

        self._assert_url_opened_with_params(
            "amsdeals@briltd.com",
            None, # No CC
            expected_subject,
            expected_body
        )

    # Add more tests:
    # - Equipment item parsing variations (e.g. missing code, missing order number)
    # - Part item parsing variations (e.g. missing location, missing part-specific charge to)
    # - What if _parse_... methods return None for an item? (generate_email should skip them)

if __name__ == '__main__':
    unittest.main(argv=['first-arg-is-ignored'], exit=False)
