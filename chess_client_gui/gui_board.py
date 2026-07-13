# chess_client_gui/gui_board.py
import tkinter as tk
from PIL import Image, ImageTk  # For handling images
import chess
import constants  # Use relative import


class GuiBoard(tk.Canvas):
    def __init__(self, master, main_app_callback, **kwargs):
        super().__init__(
            master,
            width=constants.BOARD_SIZE_PX,
            height=constants.BOARD_SIZE_PX,
            **kwargs,
        )
        self.main_app_callback = (
            main_app_callback  # To send move/click info to main app
        )
        self.board_state = chess.Board()  # Internal python-chess board
        self.player_color_perspective = chess.WHITE  # Default, can be changed
        self.selected_square_uci = None  # e.g., "e2"
        self.legal_moves_for_selected = []  # List of UCI strings for to-squares
        self.last_move_squares = []  # [from_sq_index, to_sq_index]

        self.piece_images = {}  # To store PhotoImage objects
        self._load_piece_images()

        self.bind("<Button-1>", self._on_click)
        self.draw_board_and_pieces()

    def _load_piece_images(self):
        try:
            for symbol, path in constants.PIECE_IMAGE_FILES.items():
                img = Image.open(path)
                # Resize if necessary, assuming square images for SQUARE_SIZE
                img = img.resize(
                    (constants.SQUARE_SIZE - 8, constants.SQUARE_SIZE - 8),
                    Image.Resampling.LANCZOS,
                )
                self.piece_images[symbol] = ImageTk.PhotoImage(img)
        except Exception as e:
            print(
                f"Warning: Could not load piece images: {e}. Falling back to Unicode characters."
            )
            self.piece_images = {}  # Clear it to trigger fallback

    def update_board_state(self, fen, last_move_uci=None):
        try:
            self.board_state = chess.Board(fen)
            if last_move_uci:
                move = chess.Move.from_uci(last_move_uci)
                self.last_move_squares = [move.from_square, move.to_square]
            else:
                self.last_move_squares = []
            self.draw_board_and_pieces()
        except ValueError:
            print(f"Error: Invalid FEN received: {fen}")

    def set_player_perspective(self, color_is_white):
        self.player_color_perspective = chess.WHITE if color_is_white else chess.BLACK
        self.draw_board_and_pieces()  # Redraw if perspective changes

    def _square_to_pixel(self, square_index):
        """Converts chess.Square index to top-left pixel (x,y) for drawing."""
        file = chess.square_file(square_index)
        rank = chess.square_rank(square_index)

        if self.player_color_perspective == chess.WHITE:
            # White at bottom: rank 0 is row 7, rank 7 is row 0
            # file 0 is col 0, file 7 is col 7
            col = file
            row = 7 - rank
        else:
            # Black at bottom: rank 0 is row 0, rank 7 is row 7 (flipped)
            # file 0 is col 7, file 7 is col 0 (flipped)
            col = 7 - file
            row = rank

        return col * constants.SQUARE_SIZE, row * constants.SQUARE_SIZE

    def _pixel_to_square_uci(self, x_pixel, y_pixel):
        """Converts pixel (x,y) to chess.Square uci string (e.g. "a1")."""
        col = x_pixel // constants.SQUARE_SIZE
        row = y_pixel // constants.SQUARE_SIZE

        if self.player_color_perspective == chess.WHITE:
            file_index = col
            rank_index = 7 - row
        else:  # Black's perspective
            file_index = 7 - col
            rank_index = row

        if 0 <= file_index <= 7 and 0 <= rank_index <= 7:
            return chess.square_name(chess.square(file_index, rank_index))
        return None

    def draw_board_and_pieces(self):
        self.delete("all")  # Clear canvas
        for i in range(64):  # Iterate through all squares by index
            is_light_square = (chess.square_rank(i) + chess.square_file(i)) % 2 != 0
            fill_color = (
                constants.BOARD_COLORS[0]
                if is_light_square
                else constants.BOARD_COLORS[1]
            )

            x1, y1 = self._square_to_pixel(i)
            x2, y2 = x1 + constants.SQUARE_SIZE, y1 + constants.SQUARE_SIZE
            self.create_rectangle(x1, y1, x2, y2, fill=fill_color, outline="")

            # Highlight last move
            if i in self.last_move_squares:
                self.create_rectangle(
                    x1,
                    y1,
                    x2,
                    y2,
                    fill="",
                    outline=constants.HIGHLIGHT_COLOR_PREVIOUS_MOVE,
                    width=3,
                )

            # Highlight selected square
            if (
                self.selected_square_uci
                and chess.parse_square(self.selected_square_uci) == i
            ):
                self.create_rectangle(
                    x1,
                    y1,
                    x2,
                    y2,
                    fill="",
                    outline=constants.HIGHLIGHT_COLOR_SELECTED,
                    width=3,
                )

            # Highlight legal moves for selected piece
            if self.selected_square_uci:  # Check if a piece is selected
                for move_uci_end in self.legal_moves_for_selected:
                    if chess.parse_square(move_uci_end) == i:
                        # Draw a circle or different highlight for legal moves
                        cx, cy = (
                            x1 + constants.SQUARE_SIZE / 2,
                            y1 + constants.SQUARE_SIZE / 2,
                        )
                        radius = constants.SQUARE_SIZE / 6
                        self.create_oval(
                            cx - radius,
                            cy - radius,
                            cx + radius,
                            cy + radius,
                            fill=constants.HIGHLIGHT_COLOR_LEGAL_MOVE,
                            outline="",
                        )

            # Draw piece
            piece = self.board_state.piece_at(i)
            if piece:
                symbol = piece.symbol()
                center_x, center_y = (
                    x1 + constants.SQUARE_SIZE / 2,
                    y1 + constants.SQUARE_SIZE / 2,
                )

                if self.piece_images and symbol in self.piece_images:
                    self.create_image(
                        center_x, center_y, image=self.piece_images[symbol]
                    )
                else:  # Fallback to Unicode
                    text_color = (
                        "white" if piece.color == chess.WHITE else "black"
                    )  # Example
                    self.create_text(
                        center_x,
                        center_y,
                        text=constants.UNICODE_PIECES.get(symbol, "?"),
                        font=constants.FONT_PIECE_UNICODE,
                        fill=text_color,
                    )

        # Draw rank and file labels (optional, but good for UX)
        for j in range(8):
            # Files (a-h)
            if self.player_color_perspective == chess.WHITE:
                file_char = chr(ord("a") + j)
                rank_char = str(8 - j)
            else:
                file_char = chr(ord("h") - j)
                rank_char = str(j + 1)

            self.create_text(
                j * constants.SQUARE_SIZE + constants.SQUARE_SIZE / 2,
                constants.BOARD_SIZE_PX - constants.SQUARE_SIZE / 4,  # Bottom edge
                text=file_char,
                font=("Arial", 10, "bold"),
                fill=constants.TEXT_COLOR,
            )
            # Ranks (1-8)
            self.create_text(
                constants.SQUARE_SIZE / 4,  # Left edge
                j * constants.SQUARE_SIZE + constants.SQUARE_SIZE / 2,
                text=rank_char,
                font=("Arial", 10, "bold"),
                fill=constants.TEXT_COLOR,
            )

    def _on_click(self, event):
        clicked_uci = self._pixel_to_square_uci(event.x, event.y)
        if not clicked_uci:
            return

        clicked_square_index = chess.parse_square(clicked_uci)
        piece_on_clicked_square = self.board_state.piece_at(clicked_square_index)

        if self.selected_square_uci:
            # A piece was already selected, this click is a destination
            from_uci = self.selected_square_uci
            to_uci = clicked_uci

            # Check if the target square is one of the legal moves for the selected piece
            if to_uci in self.legal_moves_for_selected:
                self.main_app_callback("ATTEMPT_MOVE", (from_uci, to_uci))
            # If clicked on the same selected piece, deselect it.
            elif from_uci == to_uci:
                self.selected_square_uci = None
                self.legal_moves_for_selected = []
            # If clicked on another of player's own pieces, select that one instead
            elif (
                piece_on_clicked_square
                and piece_on_clicked_square.color == self.board_state.turn
            ):  # Assuming main app controls turn for clicking
                self.selected_square_uci = clicked_uci
                self._update_legal_moves_for_selected()
            else:  # Clicked on an empty square not a legal move, or opponent piece not a legal move
                self.selected_square_uci = None  # Deselect
                self.legal_moves_for_selected = []

        else:  # No piece selected yet, this is the first click
            if (
                piece_on_clicked_square
                and piece_on_clicked_square.color == self.board_state.turn
            ):  # Assuming turn check
                self.selected_square_uci = clicked_uci
                self._update_legal_moves_for_selected()
            else:
                self.selected_square_uci = None
                self.legal_moves_for_selected = []

        self.draw_board_and_pieces()  # Redraw to reflect selection/highlights

    def _update_legal_moves_for_selected(self):
        self.legal_moves_for_selected = []
        if self.selected_square_uci:
            from_sq_index = chess.parse_square(self.selected_square_uci)
            for move in self.board_state.legal_moves:
                if move.from_square == from_sq_index:
                    self.legal_moves_for_selected.append(
                        chess.square_name(move.to_square)
                    )

    def deselect_piece(self):
        self.selected_square_uci = None
        self.legal_moves_for_selected = []
        self.draw_board_and_pieces()
