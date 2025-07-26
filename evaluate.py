"""
SlytherNN Evaluation Script - Fixed and Enhanced

Evaluate trained DQN agent and create demonstration GIF.
"""

import os
import torch
import numpy as np
import pygame
from typing import List, Optional
import argparse
import json

from snake_game.game import SnakeGame
from agent.dqn import DQN
from config import CHECKPOINTS_DIR, RESULTS_DIR, EvalConfig, ModelConfig, GRID_SIZE, CELL_SIZE
from utils.logging import CheckpointManager


class SnakeEvaluator:
    """Evaluate trained Snake agent and create demonstrations."""
    
    def __init__(self, checkpoint_path: Optional[str] = None):
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        print(f"Using device: {self.device}")
        
        # Load model
        self.model = self._load_model(checkpoint_path)
        
        # Initialize pygame for rendering
        pygame.init()
        self.screen = pygame.display.set_mode((GRID_SIZE * CELL_SIZE, GRID_SIZE * CELL_SIZE))
        self.clock = pygame.time.Clock()
        pygame.display.set_caption("SlytherNN: AI Evaluation")
    
    def _load_model(self, checkpoint_path: Optional[str]) -> torch.nn.Module:
        """Load the trained model from checkpoint."""
        if checkpoint_path is None:
            checkpoint_manager = CheckpointManager()
            checkpoint_path, episode = checkpoint_manager.load_latest_checkpoint()
            
            if checkpoint_path is None:
                raise FileNotFoundError("No checkpoint found. Train a model first.")
            
            print(f"Loading latest checkpoint from episode {episode}")
        
        # Create model
        model = DQN(
            input_dim=ModelConfig.INPUT_DIM, 
            output_dim=ModelConfig.OUTPUT_DIM,
            hidden_dims=ModelConfig.HIDDEN_DIMS
        )
        
        # Load checkpoint
        state = torch.load(checkpoint_path, map_location=self.device, weights_only=False)
        
        # Handle different checkpoint formats
        if isinstance(state, dict):
            if 'model' in state:
                model.load_state_dict(state['model'])
            elif 'policy_net' in state:
                model.load_state_dict(state['policy_net'])
            else:
                model.load_state_dict(state)
        else:
            model.load_state_dict(state)
        
        model.to(self.device)
        model.eval()
        
        return model
    
    def evaluate_performance(self, num_episodes: int = EvalConfig.NUM_EPISODES, 
                           verbose: bool = True) -> dict:
        """Evaluate agent performance over multiple episodes."""
        scores = []
        steps_list = []
        wins = 0
        
        for episode in range(num_episodes):
            game = SnakeGame(grid_size=GRID_SIZE, cell_size=CELL_SIZE, mode="ai")
            episode_steps = 0
            
            while game.running and episode_steps < EvalConfig.MAX_STEPS:
                state = game.get_state(self.device).flatten()
                state_tensor = state.unsqueeze(0)
                
                with torch.no_grad():
                    q_values = self.model(state_tensor)
                    action_idx = torch.argmax(q_values).item()
                
                game.ai_step(action_idx, self.device)
                episode_steps += 1
            
            scores.append(game.score)
            steps_list.append(episode_steps)
            
            if game.won:
                wins += 1
            
            if verbose:
                status = "WON" if game.won else "DIED"
                print(f"Episode {episode+1:2d}: Score={game.score:2d}, Steps={episode_steps:3d}, {status}")
        
        # Calculate statistics
        results = {
            'num_episodes': num_episodes,
            'scores': scores,
            'steps': steps_list,
            'wins': wins,
            'mean_score': np.mean(scores),
            'std_score': np.std(scores),
            'max_score': np.max(scores),
            'min_score': np.min(scores),
            'mean_steps': np.mean(steps_list),
            'win_rate': wins / num_episodes,
        }
        
        if verbose:
            print(f"\n🎯 Evaluation Results ({num_episodes} episodes):")
            print(f"  Mean Score: {results['mean_score']:.2f} ± {results['std_score']:.2f}")
            print(f"  Max Score: {results['max_score']}")
            print(f"  Win Rate: {results['win_rate']*100:.1f}%")
            print(f"  Mean Steps: {results['mean_steps']:.1f}")
        
        return results
    
    def create_demo_gif(self, output_path: str = None, max_steps: int = 500) -> str:
        """Create a GIF demonstration of the AI playing."""
        if output_path is None:
            output_path = os.path.join(RESULTS_DIR, "slythernn_demo.gif")
        
        print("🎬 Creating demonstration GIF...")
        
        # Collect frames from one game
        frames = []
        game = SnakeGame(grid_size=GRID_SIZE, cell_size=CELL_SIZE, mode="ai")
        step_count = 0
        
        while game.running and step_count < max_steps:
            # Get AI action
            state = game.get_state(self.device).flatten()
            state_tensor = state.unsqueeze(0)
            
            with torch.no_grad():
                q_values = self.model(state_tensor)
                action_idx = torch.argmax(q_values).item()
            
            # Step game
            game.ai_step(action_idx, self.device)
            step_count += 1
            
            # Render frame every few steps to reduce file size
            if step_count % 2 == 0:
                game.draw(self.screen)
                if not game.running:
                    game.draw_game_over(self.screen)
                
                # Capture frame
                frame = pygame.surfarray.array3d(self.screen)
                frame = np.transpose(frame, (1, 0, 2))  # Correct orientation
                frames.append(frame)
        
        # Create GIF using PIL
        if frames:
            self._save_gif(frames, output_path)
            status = "WON" if game.won else "DIED"
            print(f"✅ Demo completed: Score={game.score}, Steps={step_count}, {status}")
        else:
            print("❌ No frames captured!")
        
        return output_path
    
    def _save_gif(self, frames: List[np.ndarray], output_path: str):
        """Save frames as GIF using PIL."""
        try:
            from PIL import Image
            
            # Convert frames to PIL Images
            pil_frames = []
            for frame in frames:
                if frame.dtype != np.uint8:
                    frame = (frame * 255).astype(np.uint8)
                pil_frames.append(Image.fromarray(frame))
            
            # Save as GIF
            if pil_frames:
                pil_frames[0].save(
                    output_path,
                    save_all=True,
                    append_images=pil_frames[1:],
                    duration=int(1000/EvalConfig.RENDER_FPS),  # Duration in ms
                    loop=0
                )
                print(f"📁 GIF saved to: {output_path}")
            
        except ImportError:
            print("❌ PIL not available. Install with: pip install Pillow")
        except Exception as e:
            print(f"❌ Error creating GIF: {e}")
    
    def interactive_demo(self):
        """Run interactive demonstration where user can watch AI play."""
        print("🎮 Interactive Demo - Press SPACE to start new game, ESC to quit")
        
        running = True
        game = None
        
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        running = False
                    elif event.key == pygame.K_SPACE:
                        game = SnakeGame(grid_size=GRID_SIZE, cell_size=CELL_SIZE, mode="ai")
                        print("🚀 New game started!")
            
            if game and game.running:
                # AI plays
                state = game.get_state(self.device).flatten()
                state_tensor = state.unsqueeze(0)
                
                with torch.no_grad():
                    q_values = self.model(state_tensor)
                    action_idx = torch.argmax(q_values).item()
                
                game.ai_step(action_idx, self.device)
                
                if not game.running:
                    status = "WON" if game.won else "DIED"
                    print(f"🎯 Game Over! Score: {game.score}, {status}")
            
            # Render
            self.screen.fill((26, 26, 32))
            
            if game:
                game.draw(self.screen)
                if not game.running:
                    game.draw_game_over(self.screen)
            else:
                # Show start message
                font = pygame.font.Font(None, 36)
                text = font.render("Press SPACE to start", True, (255, 255, 255))
                rect = text.get_rect(center=self.screen.get_rect().center)
                self.screen.blit(text, rect)
            
            pygame.display.flip()
            self.clock.tick(EvalConfig.RENDER_FPS)
        
        pygame.quit()
    
    def save_evaluation_results(self, results: dict, filepath: str = None):
        """Save evaluation results to JSON file."""
        if filepath is None:
            filepath = os.path.join(RESULTS_DIR, "evaluation_results.json")
        
        # Convert numpy arrays to lists for JSON serialization
        json_results = {}
        for key, value in results.items():
            if isinstance(value, np.ndarray):
                json_results[key] = value.tolist()
            elif isinstance(value, (np.int64, np.float64)):
                json_results[key] = value.item()
            else:
                json_results[key] = value
        
        with open(filepath, 'w') as f:
            json.dump(json_results, f, indent=2)
        
        print(f"📊 Evaluation results saved to: {filepath}")


def main():
    """Main evaluation function."""
    parser = argparse.ArgumentParser(description="Evaluate SlytherNN agent")
    parser.add_argument("--checkpoint", type=str, help="Path to checkpoint file")
    parser.add_argument("--episodes", type=int, default=EvalConfig.NUM_EPISODES,
                       help="Number of evaluation episodes")
    parser.add_argument("--gif", action="store_true", help="Create demonstration GIF")
    parser.add_argument("--interactive", action="store_true", help="Run interactive demo")
    parser.add_argument("--output", type=str, help="Output path for GIF")
    
    args = parser.parse_args()
    
    try:
        evaluator = SnakeEvaluator(args.checkpoint)
        
        if args.interactive:
            evaluator.interactive_demo()
        else:
            # Run performance evaluation
            results = evaluator.evaluate_performance(args.episodes)
            evaluator.save_evaluation_results(results)
            
            # Create GIF if requested
            if args.gif:
                gif_path = evaluator.create_demo_gif(args.output)
                print(f"🎬 GIF saved to: {gif_path}")
    
    except Exception as e:
        print(f"❌ Error during evaluation: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())