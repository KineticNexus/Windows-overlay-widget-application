# PyQt5 Overlay Widget

This project implements a customizable overlay widget using PyQt5. It allows users to display a word at specified coordinates on the screen, creating a semi-transparent overlay that stays on top of other windows.

## Features

- Display a custom word as an overlay on the screen
- Set custom coordinates for the overlay
- Semi-transparent background
- Always-on-top functionality
- User input dialog for word and coordinates

## Requirements

- Python 3.x
- PyQt5

## Installation

1. Clone this repository:
   ```
   git clone https://github.com/yourusername/pyqt5-overlay-widget.git
   ```
2. Install the required package:
   ```
   pip install PyQt5
   ```

## Usage

Run the script using Python:

```
python overlay_widget.py
```

1. When the application starts, it will prompt you to enter a word.
2. After entering the word, you'll be asked to input X and Y coordinates for the overlay's position.
3. The overlay will appear at the specified position with the entered word.
4. To change the word or position, click the "Set Word and Coordinates" button and follow the prompts.

## How it Works

1. The application creates a `QWidget` with custom flags to make it frameless and always-on-top.
2. It uses a `QLabel` to display the text and a `QPushButton` to trigger the input dialog.
3. The `get_input` method handles user input for the word and coordinates.
4. The `show_word` method updates the label text and widget position based on user input.

## Customization

You can adjust the following aspects of the overlay:

- Font size and style in the `__init__` method
- Text color in the `setStyleSheet` call
- Overlay size in the `show_word` method

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is open source and available under the [MIT License](LICENSE).
