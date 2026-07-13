# chess_client_gui/constants.py
import os
import chess

# --- Server Configuration ---
HOST = "127.0.0.1"
PORT = 65432

# --- GUI Constants ---
SQUARE_SIZE = 60
BOARD_SIZE_PX = 8 * SQUARE_SIZE
INFO_PANEL_HEIGHT = 50
CHAT_PANEL_HEIGHT = 150
WINDOW_WIDTH = BOARD_SIZE_PX + 20  # Padding
WINDOW_HEIGHT = BOARD_SIZE_PX + INFO_PANEL_HEIGHT + CHAT_PANEL_HEIGHT + 30  # Padding

# --- Colors ---
BOARD_COLORS = ("#DDB88C", "#A66D4F")  # Light wood, Dark wood
HIGHLIGHT_COLOR_SELECTED = "#FFD700"  # Gold for selected piece
HIGHLIGHT_COLOR_LEGAL_MOVE = "#77DD77"  # Light green for legal moves
HIGHLIGHT_COLOR_PREVIOUS_MOVE = "#ADD8E6"  # Light blue for previous move
TEXT_COLOR = "black"
BACKGROUND_COLOR = "#F0F0F0"  # Main window background

# --- Fonts ---
FONT_INFO = ("Arial", 12)
FONT_CHAT = ("Arial", 10)
FONT_BUTTON = ("Arial", 10, "bold")
FONT_PIECE_UNICODE = ("Arial", 36)  # Fallback if images fail

# --- Piece Assets ---
# Assuming 'assets' folder is in the same directory as constants.py or the main script
ASSET_PATH = os.path.join(os.path.dirname(__file__), "assets")

PIECE_IMAGE_FILES = {
    "P": os.path.join(ASSET_PATH, "wp.png"),
    "N": os.path.join(ASSET_PATH, "wn.png"),
    "B": os.path.join(ASSET_PATH, "wb.png"),
    "R": os.path.join(ASSET_PATH, "wr.png"),
    "Q": os.path.join(ASSET_PATH, "wq.png"),
    "K": os.path.join(ASSET_PATH, "wk.png"),
    "p": os.path.join(ASSET_PATH, "bp.png"),
    "n": os.path.join(ASSET_PATH, "bn.png"),
    "b": os.path.join(ASSET_PATH, "bb.png"),
    "r": os.path.join(ASSET_PATH, "br.png"),
    "q": os.path.join(ASSET_PATH, "bq.png"),
    "k": os.path.join(ASSET_PATH, "bk.png"),
}

UNICODE_PIECES = {  # Fallback
    "P": "♙",
    "N": "♘",
    "B": "♗",
    "R": "♖",
    "Q": "♕",
    "K": "♔",
    "p": "♟",
    "n": "♞",
    "b": "♝",
    "r": "♜",
    "q": "♛",
    "k": "♚",
}

# --- Game Logic ---
PROMOTION_PIECES = [chess.QUEEN, chess.ROOK, chess.BISHOP, chess.KNIGHT]
PROMOTION_PIECE_SYMBOLS = {
    chess.QUEEN: "q",
    chess.ROOK: "r",
    chess.BISHOP: "b",
    chess.KNIGHT: "n",
}
