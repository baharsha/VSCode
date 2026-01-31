package com.enterprise.vedicai.data.local

import androidx.room.Database
import androidx.room.RoomDatabase

@Database(entities = [PanchangEntity::class], version = 3, exportSchema = false)
abstract class VedicDatabase : RoomDatabase() {
    abstract fun panchangDao(): PanchangDao
}
