import bcrypt from "bcryptjs"
import { db } from "./connection"
import { users, externalDatabases, customCharts, customDashboards } from "./schema"
import { eq } from "drizzle-orm"

async function main() {
  console.log("Starting seed...")

  // Create admin user
  let admin = await db.select().from(users).where(eq(users.email, "admin@example.com")).get()

  if (admin) {
    console.log("Admin user already exists, skipping...")
  } else {
    const hashedPassword = await bcrypt.hash("123456", 10)
    admin = await db.insert(users).values({
      name: "admin",
      email: "admin@example.com",
      password: hashedPassword,
      isAdmin: true,
    }).returning().get()

    console.log("Created admin user:", { id: admin.id, name: admin.name, email: admin.email })
  }

  // Create example dashboard (without external DB reference since no Docker)
  const existingDashboard = await db.select().from(customDashboards)
    .where(eq(customDashboards.name, "Example Dashboard")).get()

  if (existingDashboard) {
    console.log("Example Dashboard already exists, skipping...")
  } else {
    await db.insert(customDashboards).values({
      name: "Example Dashboard",
      renderConfig: JSON.stringify({ charts: [] }),
      createdBy: admin.id,
    })
    console.log("Created Example Dashboard")
  }

  console.log("Seed completed successfully!")
}

main().catch((e) => {
  console.error("Error during seed:", e)
  process.exit(1)
})
