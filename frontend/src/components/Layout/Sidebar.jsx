import {
  Drawer,
  List,
  ListItem,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  Toolbar,
  Divider,
} from '@mui/material'
import {
  Dashboard as DashboardIcon,
  FlightTakeoff,
  Tour,
  Analytics,
  Settings,
} from '@mui/icons-material'
import { useNavigate, useLocation } from 'react-router-dom'

const menuItems = [
  { text: 'Dashboard', icon: <DashboardIcon />, path: '/' },
  { text: 'Reservas', icon: <FlightTakeoff />, path: '/reservas' },
  { text: 'Tours', icon: <Tour />, path: '/tours' },
  { text: 'Analytics', icon: <Analytics />, path: '/analytics' },
  { text: 'Configuración', icon: <Settings />, path: '/configuracion' },
]

export default function Sidebar({ drawerWidth, mobileOpen, onClose }) {
  const navigate = useNavigate()
  const location = useLocation()

  const handleNavigation = (path) => {
    navigate(path)
    if (mobileOpen) {
      onClose()
    }
  }

  const drawer = (
    <div>
      <Toolbar>
        <img 
          src="/logo.png" 
          alt="Logo" 
          style={{ height: 40 }}
          onError={(e) => { e.target.style.display = 'none' }}
        />
      </Toolbar>
      <Divider />
      <List>
        {menuItems.map((item) => (
          <ListItem key={item.text} disablePadding>
            <ListItemButton
              selected={location.pathname === item.path}
              onClick={() => handleNavigation(item.path)}
            >
              <ListItemIcon>{item.icon}</ListItemIcon>
              <ListItemText primary={item.text} />
            </ListItemButton>
          </ListItem>
        ))}
      </List>
    </div>
  )

  return (
    <>
      {/* Mobile drawer */}
      <Drawer
        variant="temporary"
        open={mobileOpen}
        onClose={onClose}
        ModalProps={{
          keepMounted: true, // Better open performance on mobile
        }}
        sx={{
          display: { xs: 'block', sm: 'none' },
          '& .MuiDrawer-paper': {
            boxSizing: 'border-box',
            width: drawerWidth,
          },
        }}
      >
        {drawer}
      </Drawer>

      {/* Desktop drawer */}
      <Drawer
        variant="permanent"
        sx={{
          display: { xs: 'none', sm: 'block' },
          '& .MuiDrawer-paper': {
            boxSizing: 'border-box',
            width: drawerWidth,
          },
        }}
        open
      >
        {drawer}
      </Drawer>
    </>
  )
}
