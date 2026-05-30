from pygame import Color

# --- Window ---
WINDOW_WIDTH = 1024       # Game window width in pixels
WINDOW_HEIGHT = 768       # Game window height in pixels
FPS = 60                  # Target frames per second

# --- Arena ---
ARENA_PADDING = 60        # Padding from window edges to arena border
ARENA_RECT = (            # Computed arena bounding box (x, y, w, h)
    ARENA_PADDING,
    ARENA_PADDING,
    WINDOW_WIDTH - ARENA_PADDING * 2,
    WINDOW_HEIGHT - ARENA_PADDING * 2,
)

# --- Castles ---
CASTLE_SIZE = 60          # Castle bounding box size (pixels)
BRICK_SIZE = 14           # Individual brick size (pixels)
BRICKS_PER_CASTLE = 9    # Number of bricks per castle (3x3 grid)

# --- Cannon ---
CANNON_LENGTH = 24        # Cannon barrel length (pixels)
CANNON_WIDTH = 8          # Cannon barrel width (pixels)

# --- Projectiles ---
PROJECTILE_RADIUS = 6     # Ball radius (pixels)
PROJECTILE_SPEED = 8      # Base ball speed (pixels/frame)

# --- Shield ---
SHIELD_DURATION = 60      # Max shield hold time (frames) — unused if held manually
SHIELD_COOLDOWN = 180     # Frames before shield can be used again after reflecting
SHIELD_RADIUS = 50        # Shield circle radius (pixels)

# --- Combat ---
FIRE_COOLDOWN = 30        # Minimum frames between shots
MAX_PROJECTILES = 15      # Max balls in play (oldest removed when exceeded)
MAX_BLOCKADES = 4         # Max blockade clusters per castle from shield reflects

# --- Colors ---
BG_COLOR = Color(15, 15, 25)              # Window background
ARENA_COLOR = Color(40, 40, 60)           # Arena floor
ARENA_WALL_COLOR = Color(100, 100, 140)   # Arena border
BRICK_COLORS = [Color(180, 40, 40), Color(40, 140, 180), Color(40, 180, 60), Color(180, 140, 40)]  # Per-player brick colors (R, B, G, Y)
CASTLE_COLORS = [(100, 20, 20), (20, 60, 100), (20, 100, 40), (100, 80, 20)]      # Per-player castle base colors
CANNON_COLORS = [(220, 80, 80), (80, 160, 220), (80, 220, 100), (220, 180, 60)]   # Per-player cannon colors
PROJECTILE_COLORS = [(255, 80, 60), (60, 160, 255), (60, 255, 80), (255, 200, 40)] # Per-player ball colors
SHIELD_COLOR = Color(80, 180, 255, 100)   # Shield overlay color (semi-transparent)

# --- Network ---
NATS_URL = "nats://127.0.0.1:4222"       # NATS server address
# NATS_URL = "nats://demo.nats.io:4222"  # Public NATS server (shared, no auth)
NATS_NAME = "github.ryonsherman/rebound-game"  # Client identity sent to NATS on connect
NATS_PREFIX = "rebound"                   # NATS subject namespace prefix
LOBBY_COUNTDOWN = 120                     # Seconds to wait for players before match starts
STATE_HZ = 20                             # Game state broadcasts per second to clients
STATUS_HZ = 2                             # Lobby status broadcasts per second during countdown
CONNECT_TIMEOUT = 5                       # Seconds to wait for NATS connection
REQUEST_TIMEOUT = 10                      # Seconds to wait for NATS request/reply
