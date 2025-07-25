import pygame
import os
import torch
import numpy as np
from snake_game.game import SnakeGame
from agent.dqn import DQN

def get_latest_checkpoint(checkpoint_dir):
    files = [f for f in os.listdir(checkpoint_dir) if f.endswith('.pth')]
    if not files:
        return None
    files.sort(key=lambda x: int(x.split('_ep')[1].split('.pth')[0]))
    return os.path.join(checkpoint_dir, files[-1])

def main():
    pygame.init()
    grid_size = 12
    cell_size = 32
    screen_width = 600
    screen_height = 600
    grid_pixel_width = grid_size * cell_size
    board_offset_x = (screen_width - grid_pixel_width) // 2
    board_offset_y = (screen_height - grid_pixel_width) // 2

    screen = pygame.display.set_mode((screen_width, screen_height))
    clock = pygame.time.Clock()
    pygame.display.set_caption("SlytherNN: Snake RL - Menu")

    # Adaptive font size
    font_size = max(20, int(min(screen_width, screen_height) // 20))
    font = pygame.font.SysFont("arial", font_size)
    menu_text = font.render("Press [Space] for AI, [Arrow Keys] for Human", True, (255,255,255))
    menu_rect = menu_text.get_rect(center=screen.get_rect().center)
    mode = None
    while mode is None:
        screen.fill((26,26,32))
        screen.blit(menu_text, menu_rect)
        pygame.display.flip()
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit(); return
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    pygame.quit(); return
                if event.key == pygame.K_SPACE:
                    mode = "ai"
                elif event.key in (pygame.K_UP, pygame.K_DOWN, pygame.K_LEFT, pygame.K_RIGHT):
                    mode = "human"

    # Set up game and agent
    game = SnakeGame(grid_size, cell_size, mode=mode)
    ai_model = None
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print("Using device:", device)
    if mode == "ai":
        checkpoint = get_latest_checkpoint("checkpoints")
        if checkpoint:
            # Match input_dim to training: grid_size*grid_size + 4 + 2
            input_dim = grid_size * grid_size + 4 + 2
            ai_model = DQN(input_dim=input_dim, output_dim=4).to(device)
            state = torch.load(checkpoint, map_location=device, weights_only=False)
            if isinstance(state, dict) and 'model' in state:
                ai_model.load_state_dict(state['model'])
            else:
                ai_model.load_state_dict(state)
            ai_model.to(device)
            ai_model.eval()
        else:
            print("No checkpoint found. AI will not play.")

    MOVE_EVENT = pygame.USEREVENT + 1
    pygame.time.set_timer(MOVE_EVENT, 90)
    running = True
    menu_message = "Press SPACE for AI, ARROWS for Human, ESC to quit"
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                if mode == "human":
                    if event.key == pygame.K_UP:
                        game.snake.set_direction((0, -1))
                    elif event.key == pygame.K_DOWN:
                        game.snake.set_direction((0, 1))
                    elif event.key == pygame.K_LEFT:
                        game.snake.set_direction((-1, 0))
                    elif event.key == pygame.K_RIGHT:
                        game.snake.set_direction((1, 0))
                if event.key == pygame.K_r and not game.running:
                    game.reset()
            elif event.type == MOVE_EVENT and game.running:
                if mode == "ai" and ai_model:
                    state = game.get_state(device).flatten()
                    state_tensor = state.unsqueeze(0)
                    with torch.no_grad():
                        q_values = ai_model(state_tensor)
                        action_idx = torch.argmax(q_values).item()
                    game.ai_step(action_idx, device)
                else:
                    game.update()

        game.draw(screen, board_offset_x, board_offset_y)
        if not game.running:
            game.draw_game_over(screen)
        elif not game.running and mode is None:
            # Show menu message if needed
            font = pygame.font.SysFont(None, 36)
            text = font.render(menu_message, True, (255, 255, 255))
            screen.blit(text, (20, 20))
        pygame.display.flip()
        clock.tick(60)

    pygame.quit()

if __name__ == "__main__":
    main()
