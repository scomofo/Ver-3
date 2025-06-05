import tkinter as tk
from tkinter import ttk
from tkcalendar import Calendar, DateEntry
import datetime

class DatePickerWidget:
    """
    Date picker widget that can be added to any Tkinter form.
    Ensures dates are properly formatted for John Deere API (YYYY-MM-DD).
    """
    
    def __init__(self, parent, label_text="Date:", initial_date=None, on_change=None):
        """
        Initialize the date picker widget.
        
        Args:
            parent: Parent widget
            label_text (str): Label text for the date field
            initial_date (str, optional): Initial date (in YYYY-MM-DD format)
            on_change (function, optional): Callback function when date changes
        """
        self.parent = parent
        self.on_change = on_change
        self.frame = ttk.Frame(parent)
        
        # Create label
        self.label = ttk.Label(self.frame, text=label_text)
        self.label.pack(side=tk.LEFT, padx=(0, 5))
        
        # Set up initial date
        if initial_date:
            try:
                # Try to parse YYYY-MM-DD format
                date_parts = initial_date.split('-')
                if len(date_parts) == 3:
                    year, month, day = map(int, date_parts)
                    self.initial_date = datetime.date(year, month, day)
                else:
                    self.initial_date = datetime.date.today()
            except (ValueError, IndexError):
                self.initial_date = datetime.date.today()
        else:
            self.initial_date = datetime.date.today()
        
        # Create date entry widget
        self.date_var = tk.StringVar()
        self.date_entry = DateEntry(
            self.frame,
            width=12,
            background='darkblue',
            foreground='white',
            borderwidth=2,
            date_pattern='yyyy-mm-dd',  # Use ISO format for API compatibility
            textvariable=self.date_var,
            year=self.initial_date.year,
            month=self.initial_date.month,
            day=self.initial_date.day
        )
        self.date_entry.pack(side=tk.LEFT)
        
        # Set initial value
        self.set_date(self.initial_date)
        
        # Bind callback
        if self.on_change:
            self.date_var.trace_add("write", lambda *args: self.on_change())
    
    def pack(self, **kwargs):
        """Pack the frame with the given keyword arguments."""
        self.frame.pack(**kwargs)
        
    def grid(self, **kwargs):
        """Grid the frame with the given keyword arguments."""
        self.frame.grid(**kwargs)
        
    def get_date(self):
        """
        Get the selected date in YYYY-MM-DD format.
        
        Returns:
            str: Date in YYYY-MM-DD format
        """
        try:
            return self.date_var.get()
        except ValueError:
            return datetime.date.today().strftime('%Y-%m-%d')
    
    def set_date(self, date):
        """
        Set the date.
        
        Args:
            date: Date to set (can be string in YYYY-MM-DD format or datetime.date)
        """
        if isinstance(date, str):
            try:
                # Try to parse YYYY-MM-DD format
                date_parts = date.split('-')
                if len(date_parts) == 3:
                    year, month, day = map(int, date_parts)
                    date_obj = datetime.date(year, month, day)
                    self.date_entry.set_date(date_obj)
            except (ValueError, IndexError):
                pass
        elif isinstance(date, datetime.date):
            self.date_entry.set_date(date)

# Example usage
if __name__ == "__main__":
    root = tk.Tk()
    root.title("Date Picker Example")
    
    def on_date_change():
        print(f"Selected date: {date_picker.get_date()}")
    
    date_picker = DatePickerWidget(
        root, 
        label_text="Quote Date:", 
        initial_date="2025-05-08",
        on_change=on_date_change
    )
    date_picker.pack(pady=20, padx=20)
    
    # Add button to get date
    ttk.Button(
        root, 
        text="Get Date", 
        command=lambda: print(f"Current date: {date_picker.get_date()}")
    ).pack(pady=10)
    
    root.mainloop()