import {
  AppBar,
  Toolbar,
  IconButton,
  Typography,
  Box,
  Avatar,
  Menu,
  MenuItem,
  Divider,
} from '@mui/material'
import {
  Menu as MenuIcon,
  AccountCircle,
  Brightness4,
  Brightness7,
  Logout,
} from '@mui/icons-material'
import { useState } from 'react'
import { useAuth } from '../../context/AuthContext'
import { useTheme } from '../../context/ThemeContext'

export default function Navbar({ drawerWidth, onMenuClick }) {
  const { user, logout } = useAuth()
  const { mode, toggleTheme } = useTheme()
  const [anchorEl, setAnchorEl] = useState(null)

  const handleMenu = (event) => {
    setAnchorEl(event.currentTarget)
  }

  const handleClose = () => {
    setAnchorEl(null)
  }

  const handleLogout = () => {
    handleClose()
    logout()
  }

  return (
    <AppBar
      position="fixed"
      sx={{
        width: { sm: `calc(100% - ${drawerWidth}px)` },
        ml: { sm: `${drawerWidth}px` },
      }}
    >
      <Toolbar>
        <IconButton
          color="inherit"
          edge="start"
          onClick={onMenuClick}
          sx={{ mr: 2, display: { sm: 'none' } }}
        >
          <MenuIcon />
        </IconButton>

        <Typography variant="h6" noWrap component="div" sx={{ flexGrow: 1 }}>
          {import.meta.env.VITE_APP_NAME || 'Agencia Admin'}
        </Typography>

        <IconButton color="inherit" onClick={toggleTheme}>
          {mode === 'dark' ? <Brightness7 /> : <Brightness4 />}
        </IconButton>

        <IconButton
          size="large"
          onClick={handleMenu}
          color="inherit"
        >
          {user?.avatar ? (
            <Avatar src={user.avatar} sx={{ width: 32, height: 32 }} />
          ) : (
            <AccountCircle />
          )}
        </IconButton>

        <Menu
          anchorEl={anchorEl}
          anchorOrigin={{
            vertical: 'bottom',
            horizontal: 'right',
          }}
          keepMounted
          transformOrigin={{
            vertical: 'top',
            horizontal: 'right',
          }}
          open={Boolean(anchorEl)}
          onClose={handleClose}
        >
          <Box sx={{ px: 2, py: 1 }}>
            <Typography variant="subtitle1">{user?.name}</Typography>
            <Typography variant="body2" color="text.secondary">
              {user?.email}
            </Typography>
          </Box>
          <Divider />
          <MenuItem onClick={handleLogout}>
            <Logout fontSize="small" sx={{ mr: 1 }} />
            Cerrar sesión
          </MenuItem>
        </Menu>
      </Toolbar>
    </AppBar>
  )
}
