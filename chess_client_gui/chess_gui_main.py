# chess_client_gui/chess_gui_main.py
import tkinter as tk
from tkinter import scrolledtext, simpledialog, messagebox
import queue
import chess  # For chess.QUEEN etc.

# Use relative imports if running as part of a package
import constants
from gui_board import GuiBoard
from network_handler import NetworkHandler


class ChessApp:
    def __init__(self, master):
        self.master = master
        master.title("Network Chess")
        master.geometry(f"{constants.WINDOW_WIDTH}x{constants.WINDOW_HEIGHT}")
        master.configure(bg=constants.BACKGROUND_COLOR)

        self.message_queue = queue.Queue()
        self.network_handler = NetworkHandler(self.message_queue)

        self.player_side = None  # 'white' or 'black' or 'spectator'
        self.game_id = "N/A"
        self.current_server_turn = None  # 'white' or 'black'
        self.is_my_turn = False
        self.game_over = False
        self.last_move_uci_for_board = None  # Store 'e2e4'

        # --- UI Elements ---
        # Top Info Panel
        self.info_frame = tk.Frame(master, bg=constants.BACKGROUND_COLOR)
        self.info_frame.pack(pady=5, fill=tk.X, padx=10)

        self.status_label = tk.Label(
            self.info_frame,
            text="Connecting...",
            font=constants.FONT_INFO,
            bg=constants.BACKGROUND_COLOR,
            fg=constants.TEXT_COLOR,
        )
        self.status_label.pack(side=tk.LEFT, padx=5)
        self.turn_label = tk.Label(
            self.info_frame,
            text="Turn: -",
            font=constants.FONT_INFO,
            bg=constants.BACKGROUND_COLOR,
            fg=constants.TEXT_COLOR,
        )
        self.turn_label.pack(side=tk.LEFT, padx=5)
        self.player_side_label = tk.Label(
            self.info_frame,
            text="Side: -",
            font=constants.FONT_INFO,
            bg=constants.BACKGROUND_COLOR,
            fg=constants.TEXT_COLOR,
        )
        self.player_side_label.pack(side=tk.LEFT, padx=5)
        self.game_id_label = tk.Label(
            self.info_frame,
            text=f"Game ID: {self.game_id}",
            font=constants.FONT_INFO,
            bg=constants.BACKGROUND_COLOR,
            fg=constants.TEXT_COLOR,
        )
        self.game_id_label.pack(side=tk.LEFT, padx=5)

        # Chessboard
        self.gui_board = GuiBoard(
            master, self.handle_gui_board_action, bg="lightgrey"
        )  # Pass callback
        self.gui_board.pack(pady=5)

        # Chat/Log Area
        self.log_text_area = scrolledtext.ScrolledText(
            master, height=8, width=70, state=tk.DISABLED, font=constants.FONT_CHAT
        )
        self.log_text_area.pack(pady=(0, 5), padx=10, fill=tk.BOTH, expand=True)

        # Chat Input
        self.chat_input_frame = tk.Frame(master, bg=constants.BACKGROUND_COLOR)
        self.chat_input_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

        self.chat_entry = tk.Entry(
            self.chat_input_frame, width=60, font=constants.FONT_CHAT
        )
        self.chat_entry.pack(side=tk.LEFT, expand=True, fill=tk.X, ipady=2)
        self.chat_entry.bind("<Return>", self.send_chat_message_event)
        self.send_chat_button = tk.Button(
            self.chat_input_frame,
            text="Send Chat",
            command=self.send_chat_message,
            font=constants.FONT_BUTTON,
        )
        self.send_chat_button.pack(side=tk.LEFT, padx=(5, 0))

        self.master.protocol("WM_DELETE_WINDOW", self._on_closing_window)
        self._connect_and_init()
        self.process_message_queue()

    def _connect_and_init(self):
        if self.network_handler.connect(constants.HOST, constants.PORT):
            self.log_message("Attempting to connect to the server...")
        else:
            self.status_label.config(text="Failed to connect.")
            self.log_message(
                "Connection failed. Please ensure the server is running and check HOST/PORT."
            )

    def handle_gui_board_action(self, action_type, data):
        if self.game_over:
            self.log_message("Game is over. No more moves allowed.")
            return

        if action_type == "ATTEMPT_MOVE":
            if not self.is_my_turn:
                self.log_message("Not your turn.")
                self.gui_board.deselect_piece()  # Deselect if it's not their turn
                return

            from_sq_uci, to_sq_uci = data
            move_uci = from_sq_uci + to_sq_uci

            # Handle pawn promotion
            # Requires access to the internal python-chess board state on the GUI_Board
            board = self.gui_board.board_state
            try:
                parsed_move = board.parse_uci(move_uci)  # Check basic format
                piece_to_move = board.piece_at(parsed_move.from_square)

                if piece_to_move and piece_to_move.piece_type == chess.PAWN:
                    # Check if it's a promotion move by rank
                    to_rank = chess.square_rank(parsed_move.to_square)
                    if (piece_to_move.color == chess.WHITE and to_rank == 7) or (
                        piece_to_move.color == chess.BLACK and to_rank == 0
                    ):

                        promotion_choice_char = self._ask_for_promotion()
                        if promotion_choice_char:  # User made a choice
                            move_uci += promotion_choice_char
                        else:  # User cancelled promotion dialog
                            self.log_message("Promotion cancelled.")
                            self.gui_board.deselect_piece()
                            return
            except ValueError:  # Invalid UCI basic format
                self.log_message(f"Invalid move format created: {move_uci}")
                self.gui_board.deselect_piece()
                return

            self.network_handler.send_message(f"MOVE:{move_uci}")
            # self.log_message(f"Sent move: {move_uci}") # Server will confirm
            self.gui_board.deselect_piece()  # Deselect after sending attempt
            self.is_my_turn = False  # Assume turn is over until server confirms
            self.status_label.config(text="Waiting for server...")

    def _ask_for_promotion(self):
        dialog = tk.Toplevel(self.master)
        dialog.title("Pawn Promotion")
        dialog.transient(self.master)  # Keep on top
        dialog.grab_set()  # Modal
        dialog.geometry("250x150")

        tk.Label(dialog, text="Promote pawn to:", font=constants.FONT_INFO).pack(
            pady=10
        )

        choice_var = tk.StringVar(dialog)

        def on_select(piece_char):
            choice_var.set(piece_char)
            dialog.destroy()

        btn_frame = tk.Frame(dialog)
        btn_frame.pack(pady=5)

        tk.Button(
            btn_frame,
            text="Queen",
            command=lambda: on_select("q"),
            font=constants.FONT_BUTTON,
        ).pack(side=tk.LEFT, padx=5)
        tk.Button(
            btn_frame,
            text="Rook",
            command=lambda: on_select("r"),
            font=constants.FONT_BUTTON,
        ).pack(side=tk.LEFT, padx=5)
        tk.Button(
            btn_frame,
            text="Bishop",
            command=lambda: on_select("b"),
            font=constants.FONT_BUTTON,
        ).pack(side=tk.LEFT, padx=5)
        tk.Button(
            btn_frame,
            text="Knight",
            command=lambda: on_select("n"),
            font=constants.FONT_BUTTON,
        ).pack(side=tk.LEFT, padx=5)

        # Center the dialog
        self.master.update_idletasks()
        dialog_x = (
            self.master.winfo_x()
            + (self.master.winfo_width() // 2)
            - (dialog.winfo_width() // 2)
        )
        dialog_y = (
            self.master.winfo_y()
            + (self.master.winfo_height() // 2)
            - (dialog.winfo_height() // 2)
        )
        dialog.geometry(f"+{dialog_x}+{dialog_y}")

        dialog.wait_window()  # Wait for dialog to close
        return choice_var.get()

    def process_message_queue(self):
        try:
            while True:
                msg_type, data = self.message_queue.get_nowait()

                if msg_type == "LOG":
                    self.log_message(data)
                elif msg_type == "ERROR":
                    self.log_message(f"ERROR: {data}")
                    messagebox.showerror("Error", data, parent=self.master)
                elif msg_type == "DISCONNECTED":
                    self.log_message(f"Disconnected: {data}")
                    self.status_label.config(text="Disconnected from server.")
                    if not self.game_over:  # Only show if game wasn't already over
                        messagebox.showwarning(
                            "Connection Lost",
                            f"Disconnected from server: {data}",
                            parent=self.master,
                        )
                    self._cleanup_on_disconnect()
                    return  # Stop processing queue
                elif msg_type == "SERVER_MSG":
                    self._handle_server_command(data)

        except queue.Empty:
            pass  # No messages currently

        if (
            not self.network_handler.stop_threads
        ):  # Only continue polling if network is supposed to be active
            self.master.after(100, self.process_message_queue)

    def _handle_server_command(self, command):
        # self.log_message(f"[RAW CMD] {command}") # For Debugging
        if command.startswith("Welcome! Play (P) or Spectate (S)?"):
            # This initial prompt could be handled via a simpledialog or a more integrated UI later
            choice = simpledialog.askstring(
                "Game Choice", command.split("!", 1)[1].strip(), parent=self.master
            )
            if choice and choice.upper() in ["P", "S"]:
                self.network_handler.send_message(choice.upper())
                if choice.upper() == "S":
                    self.player_side = "spectator"
                    self.player_side_label.config(text="Side: Spectator")
                    self.status_label.config(text="Spectating - Choose Game")
            else:
                self.network_handler.send_message("P")  # Default to Play
                self.log_message("Defaulted to Play mode.")

        elif command.startswith("INFO:You are White."):
            self.player_side = "white"
            self.player_side_label.config(text="Side: White")
            self.gui_board.set_player_perspective(True)  # White's perspective
            self.game_id = command.split("Game ID: ")[1].split(".")[0]
            self.game_id_label.config(text=f"Game ID: {self.game_id}")
            self.status_label.config(text="Waiting for opponent...")
            self.log_message(
                f"You are White (Game ID: {self.game_id}). Waiting for opponent."
            )

        elif command.startswith("INFO:You are Black."):
            self.player_side = "black"
            self.player_side_label.config(text="Side: Black")
            self.gui_board.set_player_perspective(False)  # Black's perspective
            self.game_id = command.split("Game ID: ")[1].split(".")[0]
            self.game_id_label.config(text=f"Game ID: {self.game_id}")
            self.status_label.config(text="Game starting!")
            self.log_message(f"You are Black (Game ID: {self.game_id}). Game starting!")

        elif command.startswith("INFO:Active Games:"):  # For spectator choosing
            self.log_message(command)  # Show the list in chat/log
            spec_game_id = simpledialog.askstring(
                "Spectate Game",
                "Enter Game ID from list to spectate:",
                parent=self.master,
            )
            if spec_game_id:
                self.network_handler.send_message(spec_game_id)
            else:
                self.log_message("Spectate cancelled.")
                # Potentially close or go back to main menu if one existed

        elif command.startswith("BOARD:"):
            fen = command.split(":", 1)[1]
            self.gui_board.update_board_state(fen, self.last_move_uci_for_board)
            self.last_move_uci_for_board = None  # Clear after using it

        elif command.startswith("TURN:"):
            self.current_server_turn = command.split(":")[1].lower()
            self.turn_label.config(
                text=f"Turn: {self.current_server_turn.capitalize()}"
            )
            self.is_my_turn = (self.player_side == self.current_server_turn) and (
                self.player_side != "spectator"
            )

            if self.game_over:
                return  # Don't update status if game already flagged as over

            if self.is_my_turn:
                self.status_label.config(text="Your Turn!")
                self.master.bell()  # Audible notification
            elif self.player_side != "spectator":
                self.status_label.config(
                    text=f"Opponent's Turn ({self.current_server_turn.capitalize()})"
                )
            else:  # Spectator
                self.status_label.config(
                    text=f"Live: {self.current_server_turn.capitalize()}'s turn"
                )

        elif (
            command.startswith("INFO:Move ") and " was valid." in command
        ):  # e.g. INFO:Move e2e4 by white was valid.
            # Extract the move uci for highlighting the last move
            try:
                parts = command.split(" ")  # INFO:Move e2e4 by white was valid.
                if len(parts) > 2 and parts[0] == "INFO:Move":
                    self.last_move_uci_for_board = parts[1]
            except Exception:
                pass  # Failed to parse, no big deal for this particular info
            self.log_message(command.split("INFO:")[1].strip())

        elif command.startswith("INVALID_MOVE:"):
            reason = command.split(":", 1)[1]
            self.log_message(f"Server: {reason}")
            if self.player_side != "spectator":  # Only show popup to player
                messagebox.showwarning("Invalid Move", reason, parent=self.master)
            # Server should resend BOARD and TURN if a move was rejected, to ensure sync
            # If it was our turn and move was rejected, it's still our turn.
            if self.player_side == self.current_server_turn:  # Check if it was our turn
                self.is_my_turn = True  # Give turn back to player
                self.status_label.config(text="Your Turn (Invalid Move). Try again.")

        elif command.startswith("CHAT:"):
            self.log_message(
                command.split("CHAT:")[1].strip()
            )  # Server prepends sender info

        elif command.startswith("GAME_OVER:"):
            result = command.split(":", 1)[1]
            self.log_message(f"--- GAME OVER ---")
            self.log_message(result)
            self.status_label.config(text="Game Over!")
            self.turn_label.config(text="-")
            self.game_over = True
            self.is_my_turn = False
            messagebox.showinfo("Game Over", result, parent=self.master)

        elif command.startswith("INFO:"):  # Catch-all for other info
            self.log_message(command.split("INFO:", 1)[1].strip())
            if "Opponent disconnected" in command:
                self.status_label.config(text="Opponent Disconnected.")
                self.turn_label.config(text="-")
                self.game_over = True  # Game effectively over
                self.is_my_turn = False
            elif "Spectating Game ID" in command:
                self.status_label.config(text=command.split("INFO:", 1)[1].strip())

    def log_message(self, message):
        self.log_text_area.config(state=tk.NORMAL)
        self.log_text_area.insert(tk.END, message + "\n")
        self.log_text_area.see(tk.END)
        self.log_text_area.config(state=tk.DISABLED)

    def send_chat_message_event(self, event=None):  # Can be bound to <Return>
        self.send_chat_message()

    def send_chat_message(self):
        msg_content = self.chat_entry.get()
        if msg_content and self.network_handler:
            if self.network_handler.send_message(f"CHAT:{msg_content}"):
                self.chat_entry.delete(0, tk.END)
                # self.log_message(f"You: {msg_content}") # Server will echo with sender info
            else:
                self.log_message("Failed to send chat message (not connected?).")
        elif not self.network_handler:
            self.log_message("Network handler not available.")

    def _cleanup_on_disconnect(self):
        self.is_my_turn = False
        # Optionally disable UI elements like chat send button, board clicks etc.
        self.send_chat_button.config(state=tk.DISABLED)
        # Unbind board clicks if game is truly over or disconnected
        self.gui_board.unbind("<Button-1>")

    def _on_closing_window(self):
        if messagebox.askokcancel("Quit", "Are you sure you want to quit?"):
            self.log_message("Closing application...")
            if self.network_handler:
                self.network_handler.send_message("QUIT")  # Politely inform server
                self.network_handler.close_connection()
            self.master.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    app = ChessApp(root)
    root.mainloop()
