# Inventorium Integration
## 🎮 React Dashboard & 3D Workspace Connection

Inventorium serves as the visual frontend and 3D workspace for the Omnispindle ecosystem, providing both traditional web dashboard interfaces and immersive 3D environments for AI task management.

---

## 🎯 Overview

### What is Inventorium?
Inventorium is a React-based dashboard that transforms Omnispindle's MCP tools into a rich, interactive user experience. It includes:

- **📊 Traditional Dashboard** - Web-based project and task management
- **🎮 SwarmDesk 3D** - Immersive 3D workspace for AI coordination
- **🎭 Multi-Personality UI** - Theme system for personalized experiences
- **📱 Mobile Interface** - Responsive design for all devices
- **🤖 AI Chat Integration** - Direct Claude interaction within the dashboard

### Architecture Overview
```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Inventorium   │◄──►│   Omnispindle   │◄──►│  Claude Desktop │
│  React Frontend │    │   MCP Server    │    │   MCP Client    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
        │                       │                       │
        ▼                       ▼                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Web Browser   │    │   MongoDB       │    │  AI Assistant   │
│   (Dashboard)   │    │   Database      │    │   (Claude)      │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

---

## 🏗️ Technical Integration

### Data Flow Architecture

#### 1. Real-time Synchronization
```javascript
// MQTT connection for live updates
const mqttConnection = {
  host: 'madnessinteractive.cc',
  topics: [
    'user/{userId}/todos/updated',
    'user/{userId}/projects/changed',
    'user/{userId}/theme/switched'
  ]
};

// React Query for cached API calls
const { data: todos, refetch } = useQuery(
  ['todos', projectId],
  () => todoAPI.getTodos({ project: projectId }),
  {
    staleTime: 30000,
    refetchOnWindowFocus: true
  }
);
```

#### 2. MCP Integration Bridge
```javascript
// Service router for MCP tool calls
import todoServiceRouter from '../services/todoServiceRouter';
import { createServiceAdapter } from '../services/shared/todoInterface';

const useMCPTodos = () => {
  const createTodo = async (todoData) => {
    const context = {
      user: currentUser,
      needsUnified: hasUnifiedAccess,
      operation: 'create'
    };

    const service = todoServiceRouter.getService(context);
    const adapter = createServiceAdapter(service);
    return adapter.createTodo(todoData);
  };

  return { createTodo };
};
```

#### 3. Authentication Bridge
```javascript
// Auth0 integration with MCP context
const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [mcpContext, setMcpContext] = useState(null);

  useEffect(() => {
    if (user) {
      // Provide auth context to MCP tools
      window.authContextData = {
        currentUser: user,
        isAuthenticated: true,
        authMode: 'auth0'
      };
    }
  }, [user]);

  return (
    <AuthContext.Provider value={{ user, mcpContext }}>
      {children}
    </AuthContext.Provider>
  );
};
```

---

## 🎨 UI Component Integration

### Theme System Integration

#### 1. Component Translation
```jsx
// Before: Hardcoded strings
function TodoItem({ todo }) {
  return (
    <div>
      <h3>Create New Task</h3>
      <button>Save</button>
      <button>Cancel</button>
    </div>
  );
}

// After: Theme-aware translation
import useTranslation from '../hooks/useTranslation';

function TodoItem({ todo }) {
  const { t } = useTranslation();

  return (
    <div>
      <h3>{t('todos.create.title')}</h3>
      <button>{t('common.save')}</button>
      <button>{t('common.cancel')}</button>
    </div>
  );
}
```

#### 2. Theme Selector Integration
```jsx
// Dashboard header with theme switching
import ThemeSelector from './ThemeSelector';

function DashboardHeader() {
  return (
    <AppBar>
      <Toolbar>
        <Typography variant="h6">
          Madness Interactive Workshop
        </Typography>

        {/* Theme selector for personality switching */}
        <ThemeSelector compact={true} />

        <UserMenu />
      </Toolbar>
    </AppBar>
  );
}
```

#### 3. Dynamic Theme Application
```jsx
// Theme-aware styling
import { useResponsiveTheme } from '../utils/responsiveTheme';
import useTranslation from '../hooks/useTranslation';

function ProjectCard({ project }) {
  const themeConfig = useResponsiveTheme();
  const { t, currentTheme } = useTranslation();

  const getThemeStyles = () => {
    switch (currentTheme) {
      case 'mad-wizard':
        return {
          background: 'linear-gradient(135deg, #4a148c 0%, #6a1b9a 100%)',
          borderColor: '#ab47bc'
        };
      case 'corporate-drone':
        return {
          background: 'linear-gradient(135deg, #263238 0%, #37474f 100%)',
          borderColor: '#546e7a'
        };
      default:
        return {
          background: themeConfig.colors.background.paper,
          borderColor: themeConfig.colors.border.primary
        };
    }
  };

  return (
    <Card sx={getThemeStyles()}>
      <CardHeader title={t('projects.card.title')} />
      <CardContent>
        {t('projects.card.description')}
      </CardContent>
    </Card>
  );
}
```

---

## 🔧 API Integration Patterns

### REST API Communication

#### 1. Unified Data Service
```javascript
// todoAPI.js - HTTP client for Omnispindle
class TodoAPI {
  constructor() {
    this.baseURL = 'https://madnessinteractive.cc/api';
    this.client = axios.create({
      baseURL: this.baseURL,
      timeout: 10000
    });

    // Auth0 token injection
    this.client.interceptors.request.use(config => {
      const token = localStorage.getItem('auth0_token');
      if (token) {
        config.headers.Authorization = `Bearer ${token}`;
      }
      return config;
    });
  }

  async getTodos(params = {}) {
    const response = await this.client.get('/todos', { params });
    return response.data;
  }

  async createTodo(todoData) {
    const response = await this.client.post('/todos', todoData);
    return response.data;
  }

  async updateTodo(todoId, updates) {
    const response = await this.client.patch(`/todos/${todoId}`, updates);
    return response.data;
  }
}

export default new TodoAPI();
```

#### 2. Service Router Pattern
```javascript
// todoServiceRouter.js - Intelligent service selection
class TodoServiceRouter {
  getService(context) {
    const {
      user,
      needsUnified,
      needsAI,
      operation,
      isAuthenticated
    } = context;

    // Priority: API > MCP > Local
    if (this.isAPIAvailable() && isAuthenticated) {
      return new HTTPAPIService();
    }

    if (this.isMCPAvailable()) {
      return new MCPService();
    }

    return new LocalDatabaseService();
  }

  async performOperation(operation, params, context) {
    const service = this.getService(context);
    const adapter = createServiceAdapter(service);

    try {
      return await adapter[operation](params);
    } catch (error) {
      console.error(`Service operation failed:`, error);
      throw error;
    }
  }
}
```

#### 3. Adapter Pattern
```javascript
// shared/todoInterface.js - Unified interface
export const createServiceAdapter = (service, serviceType) => {
  return {
    async getTodos(params) {
      switch (serviceType) {
        case 'http':
          return service.get('/todos', { params });
        case 'mcp':
          return service.callTool('query_todos', params);
        case 'local':
          return service.collection('todos').find(params);
        default:
          throw new Error(`Unknown service type: ${serviceType}`);
      }
    },

    async createTodo(data) {
      const timestamp = Date.now();
      const todoData = {
        ...data,
        created_at: timestamp,
        updated_at: timestamp,
        id: generateId()
      };

      switch (serviceType) {
        case 'http':
          return service.post('/todos', todoData);
        case 'mcp':
          return service.callTool('add_todo', todoData);
        case 'local':
          return service.collection('todos').insertOne(todoData);
      }
    }
  };
};
```

---

## 📱 Multi-Platform Support

### Responsive Design Integration

#### 1. Mobile Optimization
```jsx
// Mobile-aware component rendering
import { useMobileOptimization } from '../hooks/useMobileOptimization';

function Dashboard() {
  const {
    isMobile,
    activeMobilePanel,
    switchToMobilePanel,
    shouldShowSinglePanel
  } = useMobileOptimization();

  if (isMobile) {
    return (
      <MobileDashboard
        activePanel={activeMobilePanel}
        onPanelSwitch={switchToMobilePanel}
      />
    );
  }

  return <DesktopDashboard />;
}
```

#### 2. Touch Interface Adaptation
```jsx
// Touch-optimized interactions
function TouchOptimizedTodoList({ todos }) {
  const [touchState, setTouchState] = useState({
    startX: 0,
    startY: 0,
    currentX: 0,
    isSwipping: false
  });

  const handleTouchStart = (e) => {
    const touch = e.touches[0];
    setTouchState({
      startX: touch.clientX,
      startY: touch.clientY,
      isSwipping: true
    });
  };

  const handleTouchMove = (e) => {
    if (!touchState.isSwipping) return;

    const touch = e.touches[0];
    const deltaX = touch.clientX - touchState.startX;

    if (Math.abs(deltaX) > 50) {
      // Trigger swipe action
      handleSwipeAction(deltaX > 0 ? 'right' : 'left');
    }
  };

  return (
    <div
      onTouchStart={handleTouchStart}
      onTouchMove={handleTouchMove}
      onTouchEnd={() => setTouchState({ ...touchState, isSwipping: false })}
    >
      {todos.map(todo => (
        <TodoItem key={todo.id} todo={todo} />
      ))}
    </div>
  );
}
```

---

## 🎮 3D Workspace Integration (SwarmDesk)

### Three.js Integration

#### 1. 3D Scene Setup
```javascript
// ProjectSwarmdesk.jsx - 3D environment
import * as THREE from 'three';

class SwarmDeskEnvironment {
  constructor(container, projectData) {
    this.container = container;
    this.projectData = projectData;
    this.scene = new THREE.Scene();
    this.camera = new THREE.PerspectiveCamera(75, window.innerWidth / window.innerHeight, 0.1, 1000);
    this.renderer = new THREE.WebGLRenderer({ antialias: true });

    this.initializeEnvironment();
    this.createProjectVisualization();
    this.setupInteractionHandlers();
  }

  createProjectVisualization() {
    // Create 3D representations of todos
    this.projectData.todos.forEach((todo, index) => {
      const todoMesh = this.createTodoMesh(todo);
      todoMesh.position.set(
        (index % 10) * 2 - 10,
        Math.floor(index / 10) * 2,
        0
      );
      this.scene.add(todoMesh);
    });
  }

  createTodoMesh(todo) {
    const geometry = new THREE.BoxGeometry(1, 1, 1);

    // Theme-aware materials
    const materialColor = this.getThemeColor(todo.priority);
    const material = new THREE.MeshPhongMaterial({ color: materialColor });

    const mesh = new THREE.Mesh(geometry, material);
    mesh.userData = { todo };

    return mesh;
  }

  getThemeColor(priority) {
    const { currentTheme } = useTranslation();

    const colorSchemes = {
      'mad-wizard': {
        high: 0x9c27b0,    // Mystical purple
        medium: 0x673ab7,  // Deep violet
        low: 0x3f51b5      // Arcane blue
      },
      'corporate-drone': {
        high: 0xf44336,    // Alert red
        medium: 0xff9800,  // Warning orange
        low: 0x4caf50      // Success green
      },
      'standard': {
        high: 0xff5722,    // Standard red
        medium: 0xffc107,  // Standard yellow
        low: 0x8bc34a      // Standard green
      }
    };

    return colorSchemes[currentTheme]?.[priority] || 0x808080;
  }
}
```

#### 2. Interactive Todo Management
```javascript
// 3D interaction handlers
class SwarmDeskInteraction {
  constructor(scene, camera, renderer) {
    this.scene = scene;
    this.camera = camera;
    this.renderer = renderer;
    this.raycaster = new THREE.Raycaster();
    this.mouse = new THREE.Vector2();

    this.setupEventListeners();
  }

  setupEventListeners() {
    this.renderer.domElement.addEventListener('click', this.onMouseClick.bind(this));
    this.renderer.domElement.addEventListener('mousemove', this.onMouseMove.bind(this));
  }

  onMouseClick(event) {
    this.updateMousePosition(event);

    this.raycaster.setFromCamera(this.mouse, this.camera);
    const intersects = this.raycaster.intersectObjects(this.scene.children);

    if (intersects.length > 0) {
      const selectedObject = intersects[0].object;
      const todo = selectedObject.userData.todo;

      if (todo) {
        this.handleTodoInteraction(todo, selectedObject);
      }
    }
  }

  async handleTodoInteraction(todo, mesh) {
    // Show 3D todo details panel
    this.showTodoDetails(todo, mesh.position);

    // Update todo status with theme-appropriate feedback
    const { t } = useTranslation();

    try {
      await todoAPI.updateTodo(todo.id, {
        status: 'in_progress',
        last_interaction: Date.now()
      });

      // Visual feedback in 3D space
      this.animateMeshInteraction(mesh);

      // Theme-appropriate notification
      this.showNotification(t('swarmdesk.todoInteraction.success', {
        todoTitle: todo.description
      }));
    } catch (error) {
      this.showNotification(t('swarmdesk.todoInteraction.failed'), 'error');
    }
  }
}
```

---

## 🔄 Real-time Synchronization

### MQTT Integration

#### 1. Real-time Updates
```javascript
// MQTT client for live updates
class InventoriumMQTT {
  constructor() {
    this.client = mqtt.connect('wss://madnessinteractive.cc:8084/mqtt');
    this.subscriptions = new Map();
  }

  subscribeToUserUpdates(userId) {
    const topics = [
      `user/${userId}/todos/created`,
      `user/${userId}/todos/updated`,
      `user/${userId}/todos/completed`,
      `user/${userId}/projects/changed`,
      `user/${userId}/theme/switched`
    ];

    topics.forEach(topic => {
      this.client.subscribe(topic);
      console.log(`🔔 Subscribed to ${topic}`);
    });

    this.client.on('message', this.handleMessage.bind(this));
  }

  handleMessage(topic, message) {
    const data = JSON.parse(message.toString());
    const [, userId, resource, action] = topic.split('/');

    switch (resource) {
      case 'todos':
        this.handleTodoUpdate(action, data);
        break;
      case 'projects':
        this.handleProjectUpdate(action, data);
        break;
      case 'theme':
        this.handleThemeUpdate(data);
        break;
    }
  }

  handleThemeUpdate(data) {
    // Real-time theme synchronization across tabs
    const { switchTheme } = useTranslation();

    if (data.newTheme !== data.oldTheme) {
      switchTheme(data.newTheme);
      console.log(`🎭 Theme synchronized: ${data.newTheme}`);
    }
  }
}
```

#### 2. Cross-Tab Synchronization
```javascript
// Sync state across browser tabs
const useCrossTabSync = () => {
  useEffect(() => {
    const handleStorageChange = (e) => {
      if (e.key === 'madness-theme' && e.newValue !== e.oldValue) {
        const { switchTheme } = useTranslation();
        switchTheme(e.newValue);
      }
    };

    window.addEventListener('storage', handleStorageChange);
    return () => window.removeEventListener('storage', handleStorageChange);
  }, []);
};
```

---

## 🔐 Security Integration

### Authentication Flow

#### 1. Auth0 Integration
```javascript
// Auth0 configuration
const authConfig = {
  domain: 'madness-interactive.auth0.com',
  clientId: process.env.REACT_APP_AUTH0_CLIENT_ID,
  audience: 'madness-interactive-api',
  scope: 'openid profile email offline_access'
};

const AuthProvider = ({ children }) => {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Initialize Auth0 and check existing session
    initializeAuth();
  }, []);

  const initializeAuth = async () => {
    try {
      const auth0Client = await createAuth0Client(authConfig);
      const isAuth = await auth0Client.isAuthenticated();

      if (isAuth) {
        const userData = await auth0Client.getUser();
        const token = await auth0Client.getTokenSilently();

        // Store token for API calls
        localStorage.setItem('auth0_token', token);

        setUser(userData);
        setIsAuthenticated(true);

        // Initialize MCP context
        window.authContextData = {
          currentUser: userData,
          isAuthenticated: true,
          authMode: 'auth0'
        };
      }
    } catch (error) {
      console.error('Auth initialization failed:', error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <AuthContext.Provider value={{
      isAuthenticated,
      user,
      loading,
      login: () => auth0Client.loginWithRedirect(),
      logout: () => auth0Client.logout()
    }}>
      {children}
    </AuthContext.Provider>
  );
};
```

#### 2. Protected Routes
```jsx
// Route protection with Auth0
import { Route, Navigate } from 'react-router-dom';

function ProtectedRoute({ children }) {
  const { isAuthenticated, loading } = useAuth();

  if (loading) {
    return <LoadingScreen />;
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  return children;
}

// App routing
function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/dashboard" element={
          <ProtectedRoute>
            <Dashboard />
          </ProtectedRoute>
        } />
      </Routes>
    </BrowserRouter>
  );
}
```

---

## 📊 Performance Optimization

### Lazy Loading & Code Splitting

```javascript
// Dynamic imports for large components
const ProjectSwarmdesk = lazy(() => import('./ProjectSwarmdesk'));
const EnhancedProjectMindMap = lazy(() => import('./EnhancedProjectMindMap'));
const ChatAssistant = lazy(() => import('./ChatAssistant'));

// Component with Suspense
function Dashboard() {
  return (
    <Suspense fallback={<LoadingSpinner />}>
      <Switch>
        <Route path="/swarmdesk" component={ProjectSwarmdesk} />
        <Route path="/mindmap" component={EnhancedProjectMindMap} />
        <Route path="/chat" component={ChatAssistant} />
      </Switch>
    </Suspense>
  );
}
```

### Caching Strategy

```javascript
// React Query configuration
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5 * 60 * 1000,  // 5 minutes
      cacheTime: 10 * 60 * 1000, // 10 minutes
      refetchOnWindowFocus: false,
      retry: 3
    }
  }
});

// Optimistic updates
const useOptimisticTodos = () => {
  const queryClient = useQueryClient();

  const createTodo = useMutation(todoAPI.createTodo, {
    onMutate: async (newTodo) => {
      await queryClient.cancelQueries(['todos']);

      const previousTodos = queryClient.getQueryData(['todos']);

      queryClient.setQueryData(['todos'], old => [
        ...old,
        { ...newTodo, id: 'temp-' + Date.now(), status: 'pending' }
      ]);

      return { previousTodos };
    },
    onError: (err, newTodo, context) => {
      queryClient.setQueryData(['todos'], context.previousTodos);
    },
    onSettled: () => {
      queryClient.invalidateQueries(['todos']);
    }
  });

  return { createTodo };
};
```

---

## 🚀 Deployment Integration

### Production Configuration

```javascript
// Production environment setup
const productionConfig = {
  api: {
    baseURL: 'https://madnessinteractive.cc/api',
    timeout: 30000,
    retries: 3
  },
  auth0: {
    domain: 'madness-interactive.auth0.com',
    clientId: process.env.REACT_APP_AUTH0_CLIENT_ID_PROD,
    audience: 'https://api.madnessinteractive.cc'
  },
  mqtt: {
    host: 'wss://madnessinteractive.cc:8084/mqtt',
    reconnectPeriod: 5000,
    keepalive: 60
  },
  features: {
    swarmDesk3D: true,
    voiceChat: true,
    realtimeSync: true,
    advancedAnalytics: true
  }
};
```

### CI/CD Integration

```yaml
# .github/workflows/deploy-inventorium.yml
name: Deploy Inventorium

on:
  push:
    branches: [main]
    paths: ['projects/common/Inventorium/**']

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Setup Node.js
        uses: actions/setup-node@v3
        with:
          node-version: '18'

      - name: Install dependencies
        run: |
          cd projects/common/Inventorium
          npm ci

      - name: Run tests
        run: |
          cd projects/common/Inventorium
          npm test -- --coverage

      - name: Build production
        run: |
          cd projects/common/Inventorium
          npm run build
        env:
          REACT_APP_AUTH0_CLIENT_ID: ${{ secrets.AUTH0_CLIENT_ID }}
          REACT_APP_API_BASE_URL: https://madnessinteractive.cc/api

      - name: Deploy to EC2
        run: |
          echo "${{ secrets.EC2_SSH_KEY }}" > ssh_key
          chmod 600 ssh_key
          scp -i ssh_key -r build/* ec2-user@madnessinteractive.cc:/var/www/html/
```

---

## 🎉 Conclusion

The Inventorium integration transforms Omnispindle from a backend service into a complete, interactive experience. Through careful integration of APIs, real-time synchronization, theme systems, and 3D environments, users get a seamless workflow that adapts to their personality while maintaining powerful functionality underneath.

Whether managing todos through a traditional dashboard, exploring projects in 3D space, or switching between mad wizard and corporate drone personalities, Inventorium makes AI task management both powerful and delightful.

---

**Related Documentation**:
- [Translation System Guide](./TRANSLATION_SYSTEM.md)
- [SwarmDesk 3D Integration](./SWARMDESK_INTEGRATION.md)
- [API Reference](./API_REFERENCE.md)
- [Mobile Interface Guide](./MOBILE_INTERFACE.md)