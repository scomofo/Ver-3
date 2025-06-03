"""
SharePoint Manager module for handling SharePoint operations.
Provides functionality to interact with SharePoint files via Microsoft Graph API.
"""
from typing import Optional
import requests
import os
# import requests # Duplicate import removed
import pandas as pd
from datetime import datetime
import io
import traceback
import time
import json
import logging
logger = logging.getLogger(__name__)
# ... other imports ...
# from .auth import get_access_token # Original relative import
from dotenv import load_dotenv
# *** Use RELATIVE import since auth.py is in the same 'modules' directory ***
from .auth import get_access_token # This is fine if 'auth.py' is in the same directory as sharepoint_manager.py within a package structure

# Load environment variables if not already loaded
if 'SHAREPOINT_SITE_ID' not in os.environ:
    try:
        # Assume .env is in the project root, two levels up if this file is in app/services/integrations
        # Adjust the path as per your project structure.
        # If sharepoint_manager.py is in app/services/integrations, and .env is in the root:
        dotenv_path = os.path.join(os.path.dirname(__file__), '..', '..', '.env')
        if not os.path.exists(dotenv_path):
            # If sharepoint_manager.py is in app/services (one level above integrations):
            dotenv_path = os.path.join(os.path.dirname(__file__), '..', '.env')
        if not os.path.exists(dotenv_path):
            # If sharepoint_manager.py is directly in app:
             dotenv_path = os.path.join(os.path.dirname(__file__), '.env')

        if os.path.exists(dotenv_path):
            load_dotenv(dotenv_path=dotenv_path)
            # Use logger if available, otherwise print
            log_msg = f"Loaded environment variables from {dotenv_path}"
            if logger.handlers: logger.info(log_msg)
            else: print(log_msg)
        else:
            log_msg = f"Warning: .env file not found after checking common paths relative to {__file__}"
            if logger.handlers: logger.warning(log_msg)
            else: print(log_msg)
    except Exception as e:
        log_msg = f"Warning: Could not load .env file: {e}"
        if logger.handlers: logger.warning(log_msg)
        else: print(log_msg)

class SharePointExcelManager:
    def __init__(self):
        """Initialize the SharePoint Excel Manager."""
        # Use logger if available, otherwise print
        init_msg_start = "Initializing SharePointExcelManager..."
        if logger.handlers: logger.info(init_msg_start)
        else: print(init_msg_start)

        self.is_operational = False  # Initialize the attribute

        # Get SharePoint and file information from environment variables
        self.site_id = os.environ.get('SHAREPOINT_SITE_ID')
        self.site_name = os.environ.get('SHAREPOINT_SITE_NAME', '') # Added site_name here
        self.sharepoint_url = os.environ.get('SHAREPOINT_URL', '') # Added sharepoint_url here
        self.excel_file_path = os.environ.get('FILE_PATH')  # Path to Excel file in SharePoint
        self.sender_email = os.environ.get('SENDER_EMAIL', '')

        self.local_backup_dir = os.path.join(os.path.expanduser("~"), "brideal_sp_backups") # Changed from "ams_backup" for consistency
        if not os.path.exists(self.local_backup_dir):
            try:
                os.makedirs(self.local_backup_dir)
                log_msg = f"Created local backup directory: {self.local_backup_dir}"
                if logger.handlers: logger.info(log_msg)
                else: print(log_msg)
            except Exception as e:
                log_msg = f"Warning: Could not create backup directory: {e}"
                if logger.handlers: logger.warning(log_msg)
                else: print(log_msg)

        missing_vars = []
        required_env_vars = ['SHAREPOINT_SITE_ID', 'FILE_PATH'] # SENDER_EMAIL is optional for core file ops
        for var_name in required_env_vars:
            if not os.environ.get(var_name):
                missing_vars.append(var_name)

        if missing_vars:
            log_msg = f"SharePointExcelManager: Missing required environment variables: {', '.join(missing_vars)}. Manager will not be operational."
            if logger.handlers: logger.error(log_msg)
            else: print(f"ERROR: {log_msg}")
            self.access_token = None
            return

        log_msg_sp_config = f"SharePoint config loaded: Site ID: {self.site_id}, File: {self.excel_file_path}"
        if logger.handlers: logger.info(log_msg_sp_config)
        else: print(log_msg_sp_config)

        try:
            import openpyxl # type: ignore
            log_msg_openpyxl = "openpyxl is installed and available."
            if logger.handlers: logger.debug(log_msg_openpyxl)
            else: print(log_msg_openpyxl)
        except ImportError:
            log_msg_openpyxl_err = "Required dependency 'openpyxl' is missing. SharePointExcelManager will not be operational. Please install with: pip install openpyxl"
            if logger.handlers: logger.error(log_msg_openpyxl_err)
            else: print(f"ERROR: {log_msg_openpyxl_err}")
            self.access_token = None
            return

        self.graph_base_url = "https://graph.microsoft.com/v1.0"

        try:
            self.access_token = get_access_token()
            if not self.access_token:
                log_msg_token_fail = "Failed to acquire access token during initialization. SharePoint operations will fail."
                if logger.handlers: logger.error(log_msg_token_fail)
                else: print(f"ERROR: {log_msg_token_fail}")
                # self.is_operational remains False
            else:
                log_msg_token_ok = "Successfully acquired initial access token for SharePoint operations."
                if logger.handlers: logger.info(log_msg_token_ok)
                else: print(log_msg_token_ok)
                self.is_operational = True  # Set to True on success
        except Exception as auth_err:
             log_msg_token_ex = f"Exception during initial token acquisition: {auth_err}"
             if logger.handlers: logger.error(log_msg_token_ex, exc_info=True)
             else: print(f"ERROR: {log_msg_token_ex}\n{traceback.format_exc()}")
             self.access_token = None
             # self.is_operational remains False

    def _get_headers(self):
        """
        Generate headers for Graph API requests.

        Returns:
            dict: Request headers with access token.
        """
        log_prefix = "SharePointManager (_get_headers): "
        # Refresh token if needed (or if initial acquisition failed)
        if not self.access_token:
            try:
                log_msg_refresh = "Attempting to refresh/acquire access token..."
                if logger.handlers: logger.info(f"{log_prefix}{log_msg_refresh}")
                else: print(f"{log_prefix}{log_msg_refresh}")

                self.access_token = get_access_token()
                if not self.access_token:
                    log_msg_refresh_fail = "Failed to refresh/acquire access token."
                    if logger.handlers: logger.error(f"{log_prefix}{log_msg_refresh_fail}")
                    else: print(f"ERROR: {log_prefix}{log_msg_refresh_fail}")
                    return None # Return None if token cannot be obtained
            except Exception as auth_err:
                log_msg_refresh_ex = f"Exception during token refresh/acquisition: {auth_err}"
                if logger.handlers: logger.error(f"{log_prefix}{log_msg_refresh_ex}", exc_info=True)
                else: print(f"ERROR: {log_prefix}{log_msg_refresh_ex}\n{traceback.format_exc()}")
                self.access_token = None
                return None # Return None

        return {
            'Authorization': f'Bearer {self.access_token}',
            'Content-Type': 'application/json' # Default for Graph JSON bodies
        }

    def get_excel_file_info(self):
        """
        Get information about the Excel file in SharePoint.

        Returns:
            dict: File information including ID, webUrl, etc. if found, None otherwise.
        """
        log_prefix = "SharePointManager (get_excel_file_info): "
        headers = self._get_headers()
        if headers is None:
            log_msg = "Cannot get file info without valid authentication headers."
            if logger.handlers: logger.error(f"{log_prefix}{log_msg}")
            else: print(f"ERROR: {log_prefix}{log_msg}")
            return None

        try:
            file_path = self.excel_file_path.strip('/')
            log_msg_lookup = f"Looking for file: {file_path}"
            if logger.handlers: logger.info(f"{log_prefix}{log_msg_lookup}")
            else: print(f"{log_prefix}{log_msg_lookup}")

            url = f"{self.graph_base_url}/sites/{self.site_id}/drive/root:/{file_path}" # Path needs to be URL encoded if it contains special chars
            
            response = requests.get(url, headers=headers)
            if response.status_code == 200:
                file_data = response.json()
                log_msg_found = f"Found file with ID: {file_data.get('id')}"
                if logger.handlers: logger.info(f"{log_prefix}{log_msg_found}")
                else: print(f"{log_prefix}{log_msg_found}")
                return file_data

            # If direct access fails, log it and proceed to search (original logic preserved for now)
            log_msg_direct_fail = f"Direct access to '{file_path}' failed with status {response.status_code}. Trying folder search."
            if logger.handlers: logger.warning(f"{log_prefix}{log_msg_direct_fail}")
            else: print(f"WARNING: {log_prefix}{log_msg_direct_fail}")

            parts = file_path.split('/')
            if len(parts) == 1:
                file_name = parts[0]
                search_url = f"{self.graph_base_url}/sites/{self.site_id}/drive/root/children"
            else:
                folder_path = '/'.join(parts[:-1])
                file_name = parts[-1]
                search_url = f"{self.graph_base_url}/sites/{self.site_id}/drive/root:/{folder_path}:/children" # Path needs to be URL encoded

            log_msg_search = f"Searching for {file_name} in folder via URL: {search_url}"
            if logger.handlers: logger.info(f"{log_prefix}{log_msg_search}")
            else: print(f"{log_prefix}{log_msg_search}")

            response = requests.get(search_url, headers=headers)
            response.raise_for_status() # Will raise for 4xx/5xx errors

            for item in response.json().get('value', []):
                if item.get('name') == file_name:
                    log_msg_found_search = f"Found file via search with ID: {item.get('id')}"
                    if logger.handlers: logger.info(f"{log_prefix}{log_msg_found_search}")
                    else: print(f"{log_prefix}{log_msg_found_search}")
                    return item

            log_msg_not_found = f"Excel file '{file_name}' not found in specified path after search."
            if logger.handlers: logger.error(f"{log_prefix}{log_msg_not_found}")
            else: print(f"ERROR: {log_prefix}{log_msg_not_found}")
            return None

        except Exception as e:
            log_msg_ex = f"Failed to get Excel file info: {e}"
            if logger.handlers: logger.error(f"{log_prefix}{log_msg_ex}", exc_info=True)
            else: print(f"ERROR: {log_prefix}{log_msg_ex}\n{traceback.format_exc()}")
            return None

    def get_excel_data(self, sheet_name=None):
        """
        Get current data from the Excel file.

        Args:
            sheet_name (str or int, optional): The name or index of the sheet to read.
                                               Defaults to None (reads the first sheet if 0 is not specified).
        Returns:
            pd.DataFrame: DataFrame containing the Excel data if successful, None otherwise.
        """
        log_prefix = "SharePointManager (get_excel_data): "
        graph_headers = self._get_headers() # Get Graph API JSON headers
        if graph_headers is None:
            log_msg = "Cannot get excel data without valid authentication headers."
            if logger.handlers: logger.error(f"{log_prefix}{log_msg}")
            else: print(f"ERROR: {log_prefix}{log_msg}")
            return None

        try:
            import openpyxl # type: ignore
        except ImportError:
            log_msg_openpyxl_err = "Cannot read Excel file - openpyxl package is missing."
            if logger.handlers: logger.error(f"{log_prefix}{log_msg_openpyxl_err}")
            else: print(f"ERROR: {log_prefix}{log_msg_openpyxl_err}")
            return None

        file_info = self.get_excel_file_info()
        if not file_info:
            return None # Error already logged by get_excel_file_info

        file_id = file_info.get('id')
        if not file_id:
            log_msg_no_id = "File ID not found in file_info."
            if logger.handlers: logger.error(f"{log_prefix}{log_msg_no_id}")
            else: print(f"ERROR: {log_prefix}{log_msg_no_id}")
            return None


        url = f"{self.graph_base_url}/sites/{self.site_id}/drive/items/{file_id}/content"
        log_msg_download = "Downloading Excel file content..."
        if logger.handlers: logger.info(f"{log_prefix}{log_msg_download}")
        else: print(f"{log_prefix}{log_msg_download}")
        
        # For file content download, only Authorization header is typically needed.
        # Graph API's /content endpoint usually doesn't expect 'Content-Type: application/json'.
        download_headers = {'Authorization': graph_headers['Authorization']}
        
        response = requests.get(url, headers=download_headers)
        response.raise_for_status()

        excel_data = io.BytesIO(response.content)
        try:
            current_sheet_target = sheet_name if sheet_name is not None else 0
            log_msg_parse = f"Parsing Excel data (Sheet target: {current_sheet_target})..."
            if logger.handlers: logger.info(f"{log_prefix}{log_msg_parse}")
            else: print(f"{log_prefix}{log_msg_parse}")

            df = pd.read_excel(excel_data, engine='openpyxl', sheet_name=current_sheet_target)
            log_msg_success = f"Successfully read Excel sheet with {len(df)} rows and {len(df.columns)} columns."
            if logger.handlers: logger.info(f"{log_prefix}{log_msg_success}")
            else: print(f"{log_prefix}{log_msg_success}")
            return df
        except Exception as ex:
            log_msg_ex_parse = f"Error in pandas read_excel (Target sheet: {sheet_name}): {ex}"
            if logger.handlers: logger.error(f"{log_prefix}{log_msg_ex_parse}", exc_info=True)
            else: print(f"ERROR: {log_prefix}{log_msg_ex_parse}\n{traceback.format_exc()}")
            return None

        except Exception as e:
            log_msg_ex_gen = f"Failed to get Excel data: {e}"
            if logger.handlers: logger.error(f"{log_prefix}{log_msg_ex_gen}", exc_info=True)
            else: print(f"ERROR: {log_prefix}{log_msg_ex_gen}\n{traceback.format_exc()}")
            return None

    def _update_excel_file_direct(self, updated_df, file_id, max_retries=3, retry_delay=2):
        """
        Update the Excel file directly with new data, with retry logic.

        Args:
            updated_df (pd.DataFrame): DataFrame with updated data.
            file_id (str): ID of the file to update.
            max_retries (int): Maximum number of retries.
            retry_delay (int): Delay in seconds between retries.

        Returns:
            bool: True if successful, False otherwise.
        """
        log_prefix = "SharePointManager (_update_excel_file_direct): "
        logger.info(f"{log_prefix}Entered direct Excel file update. Rows in DataFrame: {len(updated_df)}.")

        for attempt in range(max_retries):
            logger.info(f"{log_prefix}Attempt {attempt + 1}/{max_retries} to update file directly.")
            graph_headers_for_put = self._get_headers()
            if graph_headers_for_put is None:
                logger.error(f"{log_prefix}Attempt {attempt + 1}: Cannot update without valid authentication headers.")
                if attempt < max_retries - 1:
                    logger.debug(f"{log_prefix}Waiting {retry_delay}s before next attempt.")
                    time.sleep(retry_delay)
                    continue
                else:
                    logger.error(f"{log_prefix}All attempts failed due to missing auth headers.")
                    return False
            
            upload_headers = {'Authorization': graph_headers_for_put['Authorization']}
            logger.debug(f"{log_prefix}Upload headers prepared for attempt {attempt + 1}.")

            try:
                logger.info(f"{log_prefix}Converting DataFrame to Excel format (attempt {attempt + 1}/{max_retries})...")
                excel_bytes = io.BytesIO()
                updated_df.to_excel(excel_bytes, index=False, engine='openpyxl')
                excel_bytes.seek(0)
                excel_content = excel_bytes.getvalue()
                logger.debug(f"{log_prefix}DataFrame converted to {len(excel_content)} bytes of Excel data.")

                url = f"{self.graph_base_url}/sites/{self.site_id}/drive/items/{file_id}/content"
                logger.info(f"{log_prefix}Uploading updated Excel file ({len(excel_content)} bytes) to {url} (attempt {attempt+1})...")
                
                response = requests.put(url, headers=upload_headers, data=excel_content)
                logger.debug(f"{log_prefix}Direct update response status: {response.status_code}, Response text (first 200 chars): {response.text[:200]}")

                if response.status_code in (200, 201):
                    logger.info(f"{log_prefix}Successfully updated Excel file directly (attempt {attempt+1}).")
                    return True
                elif response.status_code == 423:  # Locked resource
                    logger.warning(f"{log_prefix}File is locked (attempt {attempt+1}/{max_retries}). Waiting {retry_delay}s before retry...")
                    time.sleep(retry_delay)
                    continue
                else:
                    logger.error(f"{log_prefix}Failed to update Excel file directly (attempt {attempt+1}). Status: {response.status_code}, Response: {response.text}")
                    if attempt < max_retries - 1:
                        logger.debug(f"{log_prefix}Waiting {retry_delay}s before next attempt.")
                        time.sleep(retry_delay)
                    else:
                        logger.error(f"{log_prefix}All direct update attempts failed. Last status: {response.status_code}.")
                        return False
            except Exception as e:
                logger.error(f"{log_prefix}Exception during direct Excel file update (attempt {attempt+1}/{max_retries}): {e}", exc_info=True)
                if attempt < max_retries - 1:
                    logger.debug(f"{log_prefix}Waiting {retry_delay}s before next attempt due to exception.")
                    time.sleep(retry_delay)
                else:
                    logger.error(f"{log_prefix}All direct update attempts failed due to exceptions.")
                    return False

        logger.error(f"{log_prefix}Exhausted all retries for direct file update.")
        return False

    def _update_excel_via_session(self, updated_df, file_info, target_sheet_name=None):
        """
        Update Excel using the Excel session API, appending ALL provided rows to a specified sheet.

        Args:
            updated_df (pd.DataFrame): DataFrame with ALL new rows to append.
            file_info (dict): File information including ID and parentReference.
            target_sheet_name (str, optional): The name of the sheet to append to. 
                                             If None, uses the first sheet.
        Returns:
            bool: True if successful, False otherwise.
        """
        log_prefix = "SharePointManager (_update_excel_via_session): "
        logger.info(f"{log_prefix}Attempting to update Excel via session API. Target sheet: '{target_sheet_name}', Rows to append: {len(updated_df)}.")

        session_headers = self._get_headers()
        if session_headers is None:
            logger.error(f"{log_prefix}Cannot update without valid authentication headers.")
            return False

        session_id = None
        drive_id = file_info.get('parentReference', {}).get('driveId')
        file_id = file_info.get('id')

        try:
            if not file_id or not drive_id:
                logger.error(f"{log_prefix}Missing file ID ('{file_id}') or drive ID ('{drive_id}') for Excel session API.")
                return False

            if updated_df.empty:
                logger.warning(f"{log_prefix}Updated DataFrame is empty, nothing to append.")
                return True # Considered success as there's nothing to do.

            num_cols = len(updated_df.columns)
            if num_cols == 0:
                logger.error(f"{log_prefix}DataFrame has no columns.")
                return False
            logger.debug(f"{log_prefix}DataFrame has {num_cols} columns.")

            session_url = f"{self.graph_base_url}/drives/{drive_id}/items/{file_id}/workbook/createSession"
            session_data = {"persistChanges": True}
            logger.info(f"{log_prefix}Creating Excel session...")
            session_response = requests.post(session_url, headers=session_headers, json=session_data)

            if session_response.status_code != 201:
                logger.error(f"{log_prefix}Failed to create Excel session. Status: {session_response.status_code}, Response: {session_response.text}")
                return False
            session_id = session_response.json().get('id')
            logger.info(f"{log_prefix}Created Excel session with ID: {session_id}")
            
            current_session_headers = session_headers.copy()
            current_session_headers['Workbook-Session-Id'] = session_id

            worksheet_name_to_use = target_sheet_name
            if not worksheet_name_to_use:
                logger.info(f"{log_prefix}Target sheet name not provided, fetching first worksheet name...")
                worksheets_url = f"{self.graph_base_url}/drives/{drive_id}/items/{file_id}/workbook/worksheets"
                worksheets_response = requests.get(worksheets_url, headers=current_session_headers)
                if worksheets_response.status_code != 200:
                    logger.error(f"{log_prefix}Failed to get worksheets. Status: {worksheets_response.status_code}, Response: {worksheets_response.text}")
                    raise Exception(f"Failed to get worksheets. Status: {worksheets_response.status_code}, Resp: {worksheets_response.text}")
                worksheets = worksheets_response.json().get('value', [])
                if not worksheets:
                    logger.error(f"{log_prefix}No worksheets found in the Excel file.")
                    raise Exception("No worksheets found in the Excel file.")
                worksheet_name_to_use = worksheets[0].get('name')
                logger.info(f"{log_prefix}Using first worksheet: '{worksheet_name_to_use}'")
            else:
                logger.info(f"{log_prefix}Using provided target worksheet: '{worksheet_name_to_use}'")

            logger.info(f"{log_prefix}Getting used range for worksheet '{worksheet_name_to_use}'...")
            range_url = f"{self.graph_base_url}/drives/{drive_id}/items/{file_id}/workbook/worksheets('{worksheet_name_to_use}')/usedRange(valuesOnly=true)"
            range_response = requests.get(range_url, headers=current_session_headers)
            if range_response.status_code != 200:
                logger.error(f"{log_prefix}Failed to get used range for '{worksheet_name_to_use}'. Status: {range_response.status_code}, Response: {range_response.text}")
                raise Exception(f"Failed to get used range. Status: {range_response.status_code}, Resp: {range_response.text}")
            
            range_data = range_response.json()
            current_row_count = range_data.get('rowCount', 0)
            # If sheet is empty or only has headers, usedRange might give 0 or 1.
            # If there's a header row, we want to append after it.
            # A common convention: if rowCount is 0, it's an empty sheet. If 1, it might be just headers.
            # For appending, we determine the start row based on existing content.
            # The Graph API's addRows usually appends after the last row with data.
            # However, here we are calculating the range to PATCH.
            # If current_row_count is 0, it means the sheet is entirely empty. We start at row 1 (index 0).
            # If current_row_count > 0, it means there's data. We append after the last used row.
            start_row_excel_index = current_row_count # API is 0-indexed for rows if patching a range starting at A1
                                                  # but if we get rowCount = 1 (header), next data is row index 1 (Excel row 2)

            logger.info(f"{log_prefix}Current used range in '{worksheet_name_to_use}' has {current_row_count} rows. Calculated 0-indexed start row for new data: {start_row_excel_index}.")

            end_col_letter = self._col_num_to_letter(num_cols)
            logger.debug(f"{log_prefix}End column letter for range: {end_col_letter}")

            for index, row_data in updated_df.iterrows():
                row_values_list = [row_data.tolist()]
                # Calculate the target Excel row number (1-indexed for user display, 0-indexed for API if relative to sheet start)
                current_target_excel_row_for_patch = start_row_excel_index + index # This is the 0-indexed row for the patch
                
                # Address for PATCH is 1-indexed for Excel users, e.g., A1.
                # If start_row_excel_index is 0 (empty sheet), first row is A1.
                # If start_row_excel_index is 1 (header exists), first new data row is A2.
                range_address_excel_style = f"A{current_target_excel_row_for_patch + 1}" # +1 for 1-based Excel row

                # For a single row patch, the address would be like 'Sheet1!A5:C5'
                full_range_address = f"{worksheet_name_to_use}!{range_address_excel_style}:{end_col_letter}{current_target_excel_row_for_patch + 1}"

                logger.debug(f"{log_prefix}Appending row {index + 1}/{len(updated_df)} to calculated Excel range: {full_range_address} (0-indexed row: {current_target_excel_row_for_patch})")

                update_url = f"{self.graph_base_url}/drives/{drive_id}/items/{file_id}/workbook/worksheets('{worksheet_name_to_use}')/range(address='{full_range_address}')"
                update_payload = { "values": row_values_list }

                update_response = requests.patch(update_url, headers=current_session_headers, json=update_payload)
                if update_response.status_code != 200:
                    logger.error(f"{log_prefix}Failed to update row {index + 1} at {full_range_address}. Status: {update_response.status_code}, Response: {update_response.text}")
                    raise Exception(f"Failed to update row {index+1}. Status: {update_response.status_code}, Resp: {update_response.text}")
                logger.debug(f"{log_prefix}Successfully patched row {index + 1} at {full_range_address}.")

            logger.info(f"{log_prefix}Successfully appended {len(updated_df)} rows to '{worksheet_name_to_use}' via session API.")
            return True

        except Exception as e:
            logger.error(f"{log_prefix}Failed during Excel session update: {e}", exc_info=True)
            return False
        finally:
            if session_id and drive_id and file_id:
                try:
                    log_msg_close_session = "Attempting to close session..."
                    if logger.handlers: logger.info(f"{log_prefix}{log_msg_close_session}")
                    else: print(f"{log_prefix}{log_msg_close_session}")
                    
                    close_url = f"{self.graph_base_url}/drives/{drive_id}/items/{file_id}/workbook/closeSession"
                    # For closeSession, a POST with session ID in header is needed, no body.
                    # Use a base set of headers (like self._get_headers without Content-Type if it causes issues)
                    # and add the Workbook-Session-Id.
                    base_headers_for_close = {'Authorization': self.access_token} # Minimal headers
                    if not self.access_token : # try to get it again if it became none
                         temp_h = self._get_headers()
                         if temp_h and temp_h.get('Authorization'): base_headers_for_close = {'Authorization': temp_h['Authorization']}
                         else: print(f"Warning: {log_prefix}Could not get headers to close session."); return # cannot close if no auth

                    closing_headers = base_headers_for_close.copy()
                    closing_headers['Workbook-Session-Id'] = session_id
                    
                    close_response = requests.post(close_url, headers=closing_headers)
                    if close_response.status_code == 204:
                        log_msg_close_ok = "Closed session successfully."
                        if logger.handlers: logger.info(f"{log_prefix}{log_msg_close_ok}")
                        else: print(f"{log_prefix}{log_msg_close_ok}")
                    else:
                        log_msg_close_fail = f"Failed to close session. Status: {close_response.status_code}, Resp: {close_response.text}"
                        if logger.handlers: logger.warning(f"{log_prefix}{log_msg_close_fail}")
                        else: print(f"WARNING: {log_prefix}{log_msg_close_fail}")
                except Exception as close_e:
                    log_msg_close_ex = f"Error closing session: {close_e}"
                    if logger.handlers: logger.error(f"{log_prefix}{log_msg_close_ex}", exc_info=True)
                    else: print(f"ERROR: {log_prefix}{log_msg_close_ex}\n{traceback.format_exc()}")

    def _col_num_to_letter(self, n):
        string = ""
        while n > 0:
            n, remainder = divmod(n - 1, 26)
            string = chr(65 + remainder) + string
        return string

    def _save_local_backup(self, data, filename=None):
        log_prefix = "SharePointManager (_save_local_backup): "
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename_base = filename or f"ams_backup_{timestamp}" # Consider making "ams_backup" configurable
            csv_path = os.path.join(self.local_backup_dir, f"{filename_base}.csv")
            df = pd.DataFrame(data) # Assumes data is suitable for DataFrame constructor
            df.to_csv(csv_path, index=False)
            json_path = os.path.join(self.local_backup_dir, f"{filename_base}.json")
            with open(json_path, 'w') as f:
                json.dump(data, f, indent=2) # Assumes data is JSON serializable
            log_msg = f"Local backup saved to: {csv_path} and {json_path}"
            if logger.handlers: logger.info(f"{log_prefix}{log_msg}")
            else: print(f"{log_prefix}{log_msg}")
            return csv_path
        except Exception as e:
            log_msg_ex = f"Failed to save local backup: {e}"
            if logger.handlers: logger.error(f"{log_prefix}{log_msg_ex}", exc_info=True)
            else: print(f"ERROR: {log_prefix}{log_msg_ex}\n{traceback.format_exc()}")
            return None

    def update_excel_data(self, new_data, target_sheet_name_for_append=None):
        """
        Add new rows to a specific Excel sheet with fallback options.
        If target_sheet_name_for_append is None, direct update rewrites the first sheet.
        Session update will use target_sheet_name_for_append or default to the first sheet.
        """
        log_prefix = "SharePointManager (update_excel_data): "
        logger.info(f"{log_prefix}Method called. Received {len(new_data) if new_data else 0} new data rows.")
        backup_path = None # Initialize to avoid UnboundLocalError

        try:
            if not new_data:
                logger.error(f"{log_prefix}No data provided to update Excel file.")
                return False
            
            logger.info(f"{log_prefix}Updating Excel with {len(new_data)} new rows. Target sheet for append: {target_sheet_name_for_append if target_sheet_name_for_append else 'first sheet (default for session append)'}")

            backup_path = self._save_local_backup(new_data) # This method has its own logging
            if backup_path is None:
                log_msg_backup_fail = "CRITICAL ERROR: Failed to save local backup. Aborting update."
                if logger.handlers: logger.critical(f"{log_prefix}{log_msg_backup_fail}")
                else: print(f"CRITICAL ERROR: {log_prefix}{log_msg_backup_fail}")
                return False

            file_info = self.get_excel_file_info()
            if not file_info:
                logger.critical(f"{log_prefix}CRITICAL ERROR: Failed to save local backup. Aborting update.")
                return False

            file_info = self.get_excel_file_info() # This method has its own logging
            if not file_info:
                logger.error(f"{log_prefix}Failed to get Excel file info. Update aborted. Backup available at: {backup_path}")
                return False
            file_id = file_info.get('id')

            df_for_session_append = pd.DataFrame(new_data)

            logger.info(f"{log_prefix}Attempting update via Session API...")
            session_update_success = self._update_excel_via_session(
                df_for_session_append,
                file_info,
                target_sheet_name=target_sheet_name_for_append
            )

            if session_update_success:
                logger.info(f"{log_prefix}Update successful via Session API.")
                return True
            else:
                logger.warning(f"{log_prefix}Session API append failed. Falling back to direct update (full rewrite of the first sheet)...")
            
            logger.info(f"{log_prefix}Attempting update via direct file upload (rewriting the first sheet)...")
            current_df = self.get_excel_data(sheet_name=0) # Reads the first sheet, has its own logging
            if current_df is None:
                logger.error(f"{log_prefix}Failed to get current Excel data (first sheet) for direct update. Update aborted. Backup: {backup_path}")
                return False

            new_df_prepared_for_concat = pd.DataFrame(new_data)
            if not current_df.empty and not new_df_prepared_for_concat.empty:
                logger.debug(f"{log_prefix}Aligning columns for direct update concat. Current columns: {current_df.columns.tolist()}, New data columns: {new_df_prepared_for_concat.columns.tolist()}")
                new_df_prepared_for_concat = new_df_prepared_for_concat.reindex(columns=current_df.columns)

            updated_df_for_direct = pd.concat([current_df, new_df_prepared_for_concat], ignore_index=True)
            logger.info(f"{log_prefix}DataFrame for direct upload (first sheet) has {len(updated_df_for_direct)} total rows.")

            direct_update_success = self._update_excel_file_direct(updated_df_for_direct, file_id)
            if direct_update_success:
                logger.info(f"{log_prefix}Update successful via Direct Upload (first sheet rewritten).")
                return True

            logger.warning(f"{log_prefix}Both Session API and Direct Upload failed. Data saved locally at {backup_path}")
            return False

        except Exception as e:
            logger.error(f"{log_prefix}Unhandled exception in update_excel_data: {e}", exc_info=True)
            if backup_path is None and 'new_data' in locals() and new_data is not None:
                 try:
                     backup_path_emergency = self._save_local_backup(new_data, filename="emergency_backup")
                     logger.info(f"{log_prefix}Emergency backup saved due to error: {backup_path_emergency}")
                 except Exception as backup_ex:
                     logger.error(f"{log_prefix}Failed to save emergency backup: {backup_ex}")
            return False

    def send_html_email(self, recipients, subject, html_body):
        log_prefix = "SharePointManager (send_html_email): "
        headers_for_email = self._get_headers() # Gets JSON headers
        if headers_for_email is None:
            log_msg = "Cannot send email without valid authentication headers."
            if logger.handlers: logger.error(f"{log_prefix}{log_msg}")
            else: print(f"ERROR: {log_prefix}{log_msg}")
            return False
        try:
            if not self.sender_email:
                log_msg_no_sender = "Sender email not specified in environment variables."
                if logger.handlers: logger.error(f"{log_prefix}{log_msg_no_sender}")
                else: print(f"ERROR: {log_prefix}{log_msg_no_sender}")
                return False
            if not recipients: # Expects a list of email strings
                log_msg_no_recipients = "No recipients specified for email."
                if logger.handlers: logger.error(f"{log_prefix}{log_msg_no_recipients}")
                else: print(f"ERROR: {log_prefix}{log_msg_no_recipients}")
                return False
            
            email_message = {
                "message": {
                    "subject": subject,
                    "body": {"contentType": "HTML", "content": html_body},
                    "toRecipients": [{"emailAddress": {"address": email}} for email in recipients]
                }
            }
            url = f"{self.graph_base_url}/users/{self.sender_email}/sendMail"
            response = requests.post(url, headers=headers_for_email, json=email_message) # Uses JSON headers
            if response.status_code == 202: # Accepted
                log_msg_ok = f"Successfully sent email to {len(recipients)} recipients."
                if logger.handlers: logger.info(f"{log_prefix}{log_msg_ok}")
                else: print(f"{log_prefix}{log_msg_ok}")
                return True
            else:
                log_msg_fail = f"Failed to send email. Status: {response.status_code}, Resp: {response.text}"
                if logger.handlers: logger.error(f"{log_prefix}{log_msg_fail}")
                else: print(f"ERROR: {log_prefix}{log_msg_fail}")
                return False
        except Exception as e:
            log_msg_ex = f"Failed to send email: {e}"
            if logger.handlers: logger.error(f"{log_prefix}{log_msg_ex}", exc_info=True)
            else: print(f"ERROR: {log_prefix}{log_msg_ex}\n{traceback.format_exc()}")
            return False

    def download_file_content(self, file_url: str) -> Optional[str]:
        """
        Download file content from a SharePoint URL (typically for non-Excel, e.g., CSV).
        This method attempts to use fresh headers for the request.
        
        Args:
            file_url: The SharePoint URL to the file.
            
        Returns:
            File content as string, or None if failed.
        """
        log_prefix = "SharePointManager (download_file_content): "
        
        # Get fresh headers, which includes token acquisition/refresh logic
        auth_headers = self._get_headers() 
        if auth_headers is None or 'Authorization' not in auth_headers:
            error_msg = "Failed to get valid authentication headers for file download."
            if hasattr(self, 'logger') and self.logger.handlers: self.logger.error(f"{log_prefix}{error_msg}")
            else: print(f"ERROR: {log_prefix}{error_msg}")
            return None

        # For downloading raw file content (like CSV via direct SharePoint URL, not Graph /content endpoint),
        # we generally don't need 'Content-Type: application/json'.
        # The 'Accept' header is more important to indicate what we expect.
        final_headers = {
            'Authorization': auth_headers['Authorization'],
            'Accept': 'text/plain, text/csv, application/octet-stream, */*', # Suitable for raw file content
            'User-Agent': 'BRIDeal-SharePoint-Client/2.0' # Updated User-Agent
        }
        
        try:
            log_msg_download = f"Downloading file content from: {file_url}"
            log_msg_headers = f"Request headers: {{'Authorization': 'Bearer [REDACTED]', 'Accept': '{final_headers['Accept']}', 'User-Agent': '{final_headers['User-Agent']}'}}"
            
            if hasattr(self, 'logger') and self.logger.handlers:
                self.logger.info(f"{log_prefix}{log_msg_download}")
                self.logger.debug(f"{log_prefix}{log_msg_headers}")
            else:
                print(f"{log_prefix}{log_msg_download}")
                print(f"DEBUG: {log_prefix}{log_msg_headers}")
            
            response = requests.get(file_url, headers=final_headers, timeout=30)
            
            log_msg_status = f"Response status: {response.status_code}"
            if hasattr(self, 'logger') and self.logger.handlers: self.logger.debug(f"{log_prefix}{log_msg_status}")
            else: print(f"DEBUG: {log_prefix}{log_msg_status}")
            
            if response.status_code == 200:
                # Try to decode with utf-8-sig first to handle BOM, then fallback
                try:
                    content = response.content.decode('utf-8-sig')
                except UnicodeDecodeError:
                    content = response.text # Fallback to requests' auto-detection

                success_msg = f"Successfully downloaded file content: {len(content)} characters"
                if hasattr(self, 'logger') and self.logger.handlers: self.logger.info(f"{log_prefix}{success_msg}")
                else: print(f"SUCCESS: {log_prefix}{success_msg}")
                
                lines = content.splitlines()[:3] # Use splitlines() for better line splitting
                log_msg_preview = f"First 3 lines of downloaded content: {lines}"
                if hasattr(self, 'logger') and self.logger.handlers: self.logger.debug(f"{log_prefix}{log_msg_preview}")
                else: print(f"DEBUG: {log_prefix}{log_msg_preview}")
                return content
            
            # Specific error handling based on status code
            error_text_preview = response.text[:500] if response.text else "No response text"
            if response.status_code == 401:
                error_msg = "Authentication failed - access token may be invalid or expired for this resource."
            elif response.status_code == 403:
                error_msg = "Access forbidden - check SharePoint permissions for this file/URL."
            elif response.status_code == 404:
                error_msg = f"File not found at URL: {file_url}"
            else:
                error_msg = f"Failed to download file. Status: {response.status_code}. Response: {error_text_preview}"
            
            if hasattr(self, 'logger') and self.logger.handlers: self.logger.error(f"{log_prefix}{error_msg}")
            else: print(f"ERROR: {log_prefix}{error_msg}")
            return None
                
        except requests.exceptions.Timeout:
            error_msg = f"Timeout downloading file from {file_url}"
            if hasattr(self, 'logger') and self.logger.handlers: self.logger.error(f"{log_prefix}{error_msg}")
            else: print(f"ERROR: {log_prefix}{error_msg}")
            return None
        except requests.exceptions.RequestException as e:
            error_msg = f"Request error downloading file from {file_url}: {e}"
            if hasattr(self, 'logger') and self.logger.handlers: self.logger.error(f"{log_prefix}{error_msg}")
            else: print(f"ERROR: {log_prefix}{error_msg}")
            return None
        except Exception as e:
            error_msg = f"Unexpected error downloading file content from {file_url}: {e}"
            if hasattr(self, 'logger') and self.logger.handlers: self.logger.error(f"{log_prefix}{error_msg}", exc_info=True)
            else: print(f"ERROR: {log_prefix}{error_msg}\n{traceback.format_exc()}")
            return None

if __name__ == "__main__":
    # Configure a basic logger for __main__ testing
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(name)s - [%(module)s.%(funcName)s:%(lineno)d] - %(message)s')
    main_logger = logging.getLogger(__name__)
    main_logger.info("Testing SharePoint Excel Manager...")
    
    manager = SharePointExcelManager()
    
    if manager.is_operational:
        main_logger.info("SharePointExcelManager appears operational.")
        
        # Test downloading a CSV file (replace with an actual CSV URL in your SharePoint)
        # Ensure this CSV file path is configured in your .env or it's publicly accessible for unauth test
        csv_test_url = os.environ.get("SHAREPOINT_CSV_TEST_URL") # Add this to your .env for testing
        if csv_test_url:
            main_logger.info(f"Attempting to download CSV content from: {csv_test_url}")
            csv_content = manager.download_file_content(csv_test_url)
            if csv_content:
                main_logger.info(f"Successfully downloaded CSV content ({len(csv_content)} chars). Preview: {csv_content[:200]}...")
            else:
                main_logger.error("Failed to download CSV content.")
        else:
            main_logger.warning("SHAREPOINT_CSV_TEST_URL not set in .env, skipping CSV download test.")

        # Original Excel file info and data tests (Graph API based)
        file_info = manager.get_excel_file_info() # Uses Graph API
        if file_info:
            main_logger.info(f"Successfully found Excel file via Graph: {file_info.get('name')}")
            df_first = manager.get_excel_data(sheet_name=0) # Reads first sheet via Graph API
            if df_first is not None:
                main_logger.info(f"Successfully read first Excel sheet via Graph with {len(df_first)} rows and {len(df_first.columns)} columns.")
                main_logger.info(f"Column names: {list(df_first.columns)}")
            else:
                main_logger.error("Failed to read first Excel sheet via Graph.")
        else:
            main_logger.error("Failed to get Excel file info via Graph.")
    else:
        main_logger.error("SharePointExcelManager is NOT operational. Check logs and .env configuration.")