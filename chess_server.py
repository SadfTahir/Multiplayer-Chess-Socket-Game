import socket
import threading
import chess
import uuid  # For unique game IDs

HOST = "127.0.0.1"
PORT = 65432
MAX_SPECTATORS_PER_GAME = 5

active_games = {}
waiting_players = []
lock = threading.Lock()


def generate_game_id():
    return str(uuid.uuid4())[:8]


# Helper function to check for game over conditions
def check_game_over(board, player_who_moved_color):
    if board.is_checkmate():
        return f"GAME_OVER:Checkmate! Winner: {player_who_moved_color}\n"
    if board.is_stalemate():
        return "GAME_OVER:Stalemate! It's a draw.\n"
    if board.is_insufficient_material():
        return "GAME_OVER:Insufficient material! It's a draw.\n"
    if board.is_seventyfive_moves():
        return "GAME_OVER:75-move rule! It's a draw.\n"
    if board.is_fivefold_repetition():
        return "GAME_OVER:Fivefold repetition! It's a draw.\n"
    return None


def broadcast(game_id, message, exclude_conn=None):
    game = active_games.get(game_id)
    if not game:
        return

    for color, player_conn in game["players"].items():
        if player_conn and player_conn != exclude_conn:
            try:
                player_conn.sendall(message.encode())
            except socket.error as e:
                print(f"[BROADCAST ERROR to Player {color}]: {e}")
                # Consider marking player for removal or handling disconnect here

    # Make a copy for safe iteration if spectators might be removed due to send errors
    # However, removal is best handled by the spectator's own thread or a more robust cleanup.
    # For now, just try to send.
    current_spectators = list(game["spectators"])  # Iterate over a copy
    for spec_conn in current_spectators:
        if spec_conn != exclude_conn:
            try:
                spec_conn.sendall(message.encode())
            except socket.error as e:
                print(f"[BROADCAST ERROR to Spectator]: {e}")
                # If a spectator send fails, their own handler thread should eventually detect and clean up.
                # Or, we could remove them here (requires careful lock management if modifying game["spectators"])


def handle_client(conn, addr):
    print(f"[NEW CONNECTION] {addr} connected.")
    player_game_id = None
    player_color = None
    is_spectator = False

    try:
        conn.sendall("Welcome! Play (P) or Spectate (S)? ".encode())
        choice = conn.recv(1024).decode().strip().upper()

        with lock:
            if choice == "P":
                # ... (Your existing player matchmaking logic - seems okay)
                if not waiting_players:
                    game_id = generate_game_id()
                    player_game_id = game_id
                    player_color = "white"
                    active_games[game_id] = {
                        "board": chess.Board(),
                        "players": {"white": conn, "black": None},
                        "spectators": [],
                        "turn": "white",
                        "player_addrs": {"white": addr, "black": None},
                    }
                    waiting_players.append(game_id)
                    conn.sendall(
                        f"INFO:You are White. Game ID: {game_id}. Waiting for an opponent...\n".encode()
                    )
                    print(
                        f"[GAME {game_id}] Player {addr} is White. Waiting for Black."
                    )
                else:
                    game_id = waiting_players.pop(0)
                    player_game_id = game_id
                    player_color = "black"
                    game = active_games[game_id]
                    game["players"]["black"] = conn
                    game["player_addrs"]["black"] = addr
                    conn.sendall(
                        f"INFO:You are Black. Game ID: {game_id}. Game starting with {game['player_addrs']['white']}!\n".encode()
                    )
                    if game["players"]["white"]:
                        game["players"]["white"].sendall(
                            f"INFO:Player {addr} (Black) has joined. Game starts!\n".encode()
                        )
                    print(
                        f"[GAME {game_id}] Player {addr} is Black. Game starts with {game['player_addrs']['white']}."
                    )
                    broadcast(game_id, f"BOARD:{game['board'].fen()}\n")
                    broadcast(game_id, f"TURN:{game['turn']}\n")

            elif choice == "S":
                is_spectator = True
                if not active_games:  # Check if there are any games AT ALL
                    conn.sendall(
                        "INFO:No active games to spectate. Try again later.\n".encode()
                    )
                    return  # Close connection for this would-be spectator

                # Filter for games that are actually joinable by a spectator (e.g. have at least one player or are in progress)
                # For simplicity, listing all games with some status for now.
                displayable_games = {
                    gid: gdata
                    for gid, gdata in active_games.items()
                    if gdata["players"]["white"]
                }  # Example: only list if white is there

                if not displayable_games:
                    conn.sendall(
                        "INFO:No games currently available for spectating. Try again later.\n".encode()
                    )
                    return

                games_list_str = "INFO:Active Games:\n"
                for (
                    gid,
                    g_data,
                ) in displayable_games.items():  # Iterate over displayable games
                    white_player_addr = g_data["player_addrs"]["white"]
                    black_player_addr = g_data["player_addrs"].get("black", "N/A")
                    status = (
                        "Waiting for Black"
                        if not g_data["players"]["black"]
                        else "In Progress"
                    )
                    games_list_str += f"  ID: {gid} - White: {white_player_addr} vs Black: {black_player_addr} ({status})\n"
                games_list_str += "Enter Game ID to spectate: "
                conn.sendall(games_list_str.encode())

                spec_game_id_choice = conn.recv(1024).decode().strip()

                if spec_game_id_choice in active_games:  # Check original active_games
                    game_to_spectate = active_games[spec_game_id_choice]
                    if len(game_to_spectate["spectators"]) < MAX_SPECTATORS_PER_GAME:
                        game_to_spectate["spectators"].append(conn)
                        player_game_id = spec_game_id_choice
                        conn.sendall(
                            f"INFO:Spectating Game ID {spec_game_id_choice}. Board updates will follow.\n".encode()
                        )
                        conn.sendall(f"BOARD:{game_to_spectate['board'].fen()}\n")
                        conn.sendall(f"TURN:{game_to_spectate['turn']}\n")
                        print(
                            f"[SPECTATOR] {addr} is now spectating game {spec_game_id_choice}"
                        )
                    else:
                        conn.sendall(
                            "INFO:Spectator limit reached for this game.\n".encode()
                        )
                        return
                else:
                    conn.sendall("INFO:Invalid Game ID.\n".encode())
                    return
            else:  # Invalid initial choice
                conn.sendall("INFO:Invalid choice.\n".encode())
                return  # Close connection

        # Main processing loop for the client
        while True:
            if (
                not player_game_id
            ):  # If no game assigned (e.g. spectator failed to join, or player quit)
                break  # Exit main loop, leads to finally

            if player_game_id not in active_games:
                # Game might have ended and been cleaned up by another thread
                if (
                    not is_spectator
                ):  # Only send to players, spectators might get this if game ends while they join
                    conn.sendall(
                        "INFO:The game session has ended or is no longer available.\n".encode()
                    )
                print(
                    f"[{'SPECTATOR' if is_spectator else 'PLAYER'}] {addr} found game {player_game_id} no longer active."
                )
                break  # Exit main loop

            game = active_games[player_game_id]  # Game is active

            if is_spectator:
                # --- FIXED SPECTATOR LOOP ---
                spectator_is_connected = True
                # print(f"[SPECTATOR DEBUG] {addr} entered monitoring loop for game {player_game_id}.")
                while spectator_is_connected:
                    try:
                        conn.settimeout(20.0)  # How often to check connection status
                        received_data = conn.recv(
                            1
                        )  # Attempt to read 1 byte; blocks until data or timeout

                        if not received_data:
                            # Client closed connection gracefully
                            print(
                                f"[SPECTATOR] {addr} (Game: {player_game_id}) closed connection (recv empty)."
                            )
                            spectator_is_connected = (
                                False  # Signal to exit monitoring loop
                            )
                        else:
                            # Spectator sent unexpected data. This shouldn't happen.
                            print(
                                f"[SPECTATOR] {addr} (Game: {player_game_id}) sent unexpected data: {received_data.decode(errors='ignore')}. Ignoring."
                            )
                            # Loop continues, data is consumed.
                    except socket.timeout:
                        # This is normal for an idle spectator. Connection is still alive.
                        pass  # Continue monitoring loop
                    except (socket.error, ConnectionResetError, BrokenPipeError) as e:
                        print(
                            f"[SPECTATOR] {addr} (Game: {player_game_id}) connection error: {e}. Disconnecting."
                        )
                        spectator_is_connected = False  # Signal to exit monitoring loop
                    except Exception as e:  # Catch any other unexpected error
                        print(
                            f"[SPECTATOR] {addr} (Game: {player_game_id}) unexpected error in monitoring: {e}. Disconnecting."
                        )
                        spectator_is_connected = False  # Signal to exit monitoring loop

                # If spectator_is_connected became False, break from the main 'handle_client' while True loop.
                # This will lead to the 'finally' block for cleanup.
                break
                # --- END OF FIXED SPECTATOR LOOP ---

            else:  # It's a player
                if (
                    game["players"].get(player_color) == conn
                    and game["turn"] == player_color
                ):
                    conn.sendall("YOUR_TURN:\n".encode())

                data = conn.recv(1024).decode().strip()
                if not data:
                    print(
                        f"[DISCONNECTED] Player {addr} ({player_color}, Game: {player_game_id}) sent empty data, assuming disconnect."
                    )
                    break

                print(
                    f"[GAME {player_game_id}] Received from player {addr} ({player_color}): {data}"
                )

                if data.startswith("MOVE:"):
                    if game["turn"] != player_color:
                        conn.sendall("INVALID_MOVE:Not your turn.\n".encode())
                        continue
                    if not game["players"]["white"] or not game["players"]["black"]:
                        conn.sendall(
                            "INVALID_MOVE:Opponent not connected yet.\n".encode()
                        )
                        continue

                    move_uci = data.split(":")[1]
                    try:
                        move_obj = game["board"].parse_uci(
                            move_uci
                        )  # Use a different var name
                        if move_obj in game["board"].legal_moves:
                            game["board"].push(move_obj)

                            broadcast(player_game_id, f"BOARD:{game['board'].fen()}\n")

                            # Send move confirmation BEFORE turn/game_over broadcast
                            last_move_info = (
                                f"INFO:Move {move_uci} by {player_color} was valid.\n"
                            )
                            broadcast(player_game_id, last_move_info)

                            # Switch turn *after* sending move info but *before* game over check by new player's turn
                            game["turn"] = (
                                "black" if player_color == "white" else "white"
                            )

                            game_over_message = check_game_over(
                                game["board"], player_color
                            )  # player_color is the one who made the winning move
                            if game_over_message:
                                broadcast(player_game_id, game_over_message)
                                print(
                                    f"[GAME {player_game_id}] Game Over. {game_over_message.strip()}"
                                )
                                with lock:  # Ensure thread-safe deletion
                                    if player_game_id in active_games:
                                        del active_games[player_game_id]
                                break  # End client handler loop for this player
                            else:
                                broadcast(player_game_id, f"TURN:{game['turn']}\n")
                        else:
                            conn.sendall("INVALID_MOVE:Illegal move.\n".encode())
                    except ValueError:
                        conn.sendall(
                            "INVALID_MOVE:Invalid move format (use UCI e.g., e2e4).\n".encode()
                        )
                    except Exception as e:
                        print(f"[ERROR processing move for {addr}]: {e}")
                        conn.sendall("ERROR:Could not process move.\n".encode())

                elif data.startswith("CHAT:"):
                    chat_msg = data.split(":", 1)[1]
                    broadcast(
                        player_game_id,
                        f"CHAT:{player_color}({addr}): {chat_msg}\n",
                        exclude_conn=conn,
                    )
                    conn.sendall(
                        f"CHAT:You: {chat_msg}\n".encode()
                    )  # Echo chat to self

                elif data.upper() == "QUIT":
                    conn.sendall("INFO:You have quit the game.\n".encode())
                    break  # Player initiated quit

                else:  # Unrecognized command from player
                    if game["turn"] != player_color:
                        conn.sendall(
                            "INFO:It's not your turn. Type 'CHAT:<your message>' to chat or 'QUIT'.\n".encode()
                        )
                    # else: # Player's turn but sent garbage
                    # conn.sendall("INFO:Unknown command. Use MOVE:uci, CHAT:msg, or QUIT.\n".encode())

    except socket.error as e:
        print(f"[SOCKET ERROR for {addr}]: {e}")
    except Exception as e:
        print(f"[UNEXPECTED ERROR for {addr}]: {e}")
    finally:
        print(
            f"[CLEANUP] Cleaning up connection for {addr} (Game ID: {player_game_id}, Spectator: {is_spectator})"
        )
        with lock:
            if player_game_id and player_game_id in active_games:
                current_game = active_games.get(player_game_id)  # Re-fetch under lock
                if current_game:  # Check if game still exists
                    if is_spectator:
                        if conn in current_game["spectators"]:
                            current_game["spectators"].remove(conn)
                            print(
                                f"[SPECTATOR] {addr} removed from game {player_game_id}"
                            )
                    else:  # It's a player
                        # Notify opponent if they are still there
                        opponent_color = "black" if player_color == "white" else "white"
                        opponent_conn = current_game["players"].get(opponent_color)
                        if opponent_conn:
                            try:
                                opponent_conn.sendall(
                                    f"INFO:Opponent ({player_color} at {addr}) disconnected. Game may have ended.\n".encode()
                                )
                            except socket.error:
                                print(
                                    f"[CLEANUP] Error sending disconnect to opponent of {addr}."
                                )

                        # If a player disconnects, the game might be considered over
                        # and removed. Check if it's still there before trying to delete.
                        print(
                            f"[PLAYER DISCONNECT] Player {player_color} ({addr}) disconnected from game {player_game_id}."
                        )
                        # Game might have already been deleted if game_over was reached.
                        # A simple approach: just try to remove the player from their slot if game exists.
                        # If both players gone, game might be stale. A more robust system would handle this.
                        if current_game["players"].get(player_color) == conn:
                            current_game["players"][
                                player_color
                            ] = None  # Vacate the slot

                        # If no players left, or game explicitly ended, remove the game.
                        # For simplicity, if one player disconnects and game over wasn't triggered, the game becomes unplayable.
                        # The game deletion logic is currently tied to game_over.
                        # A more advanced server might declare a win for the remaining player or end the game.
                        # For now, the primary deletion happens on explicit game_over.
                        # If player quits, game object might remain until server restart or more logic added.
                        # However, the 'player_game_id not in active_games' check at loop start helps.

                        # If the game object is still in active_games AND this disconnecting player was the last one,
                        # or if we decide any player disconnect ends game that wasn't formally over.
                        if (
                            not current_game["players"]["white"]
                            and not current_game["players"]["black"]
                        ):
                            print(
                                f"[CLEANUP] Game {player_game_id} has no players left. Removing from active_games."
                            )
                            del active_games[player_game_id]
                        elif (
                            player_game_id in active_games
                            and current_game["players"].get(player_color) is None
                        ):  # Player slot is now None
                            # Check if the *other* player is also None. If so, game is truly empty.
                            other_player_conn = current_game["players"].get(
                                opponent_color
                            )
                            if other_player_conn is None:
                                print(
                                    f"[CLEANUP] Both player slots empty in game {player_game_id}. Removing from active_games."
                                )
                                del active_games[player_game_id]

            # If the player was in the waiting queue and disconnected
            if (
                not is_spectator
                and player_color == "white"
                and conn
                == active_games.get(player_game_id, {}).get("players", {}).get("white")
            ):
                # This player was 'white' and potentially in waiting_players if game didn't start
                if player_game_id in waiting_players:
                    waiting_players.remove(player_game_id)
                    print(
                        f"[LOBBY] Player {addr} removed from waiting queue for game {player_game_id}."
                    )
                    # Also remove the partial game object if it was created for waiting
                    if player_game_id in active_games:
                        del active_games[player_game_id]
                        print(f"[LOBBY] Partial game {player_game_id} removed.")

        conn.close()
        print(f"[CONNECTION CLOSED] {addr}")


def start_server():
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind((HOST, PORT))
    server_socket.listen()  # Default backlog is fine for this scale
    print(f"Chess server listening on {HOST}:{PORT}")

    try:
        while True:
            conn, addr = server_socket.accept()
            thread = threading.Thread(target=handle_client, args=(conn, addr))
            thread.daemon = True
            thread.start()
    except KeyboardInterrupt:
        print("\n[SERVER SHUTDOWN] Server is shutting down.")
    finally:
        # Close all active client connections and games (optional, as daemon threads will die)
        print("[SERVER SHUTDOWN] Cleaning up active games...")
        with lock:
            for game_id in list(active_games.keys()):  # Iterate over a copy of keys
                game = active_games.pop(game_id, None)
                if game:
                    for p_conn in game["players"].values():
                        if p_conn:
                            try: 
                                p_conn.close()
                            except:
                                pass  # ignore errors on close
                    for s_conn in game["spectators"]:
                        if s_conn:
                            try:
                                s_conn.close()
                            except:
                                pass  # ignore errors on close
        print("[SERVER SHUTDOWN] Server has shut down.")
        if server_socket:
            server_socket.close()


if __name__ == "__main__":
    start_server()


