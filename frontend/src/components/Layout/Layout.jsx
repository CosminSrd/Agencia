import { Outlet } from 'react-router-dom'
import { Box } from '@mui/material'
import Navbar from './Navbar'
import Sidebar from './Sidebar'
import { useState } from 'react'

const drawerWidth = 240

export default function Layout() {
  const [mobileOpen, setMobileOpen] = useState(false)

  const handleDrawerToggle = () => {
    setMobileOpen(!mobileOpen)
  }

  return (
    <Box sx={{ display: 'flex', minHeight: '100vh' }}>
      <Navbar 
        drawerWidth={drawerWidth} 
        onMenuClick={handleDrawerToggle} 
      />
      
      <Sidebar
        drawerWidth={drawerWidth}
        mobileOpen={mobileOpen}
        onClose={handleDrawerToggle}
      />
      
      <Box
        component="main"
        sx={{
          flexGrow: 1,
          p: 3,
          width: { sm: `calc(100% - ${drawerWidth}px)` },
          mt: 8,
        }}
      >
        <Outlet />
      </Box>
    </Box>
  )
}
