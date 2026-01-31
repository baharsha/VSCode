package com.enterprise.vedicai.data.local

import androidx.room.Dao
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query

@Dao
interface PanchangDao {
    @Query("SELECT * FROM panchang_cache WHERE date = :date")
    suspend fun getPanchangForDate(date: String): PanchangEntity?

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertPanchang(panchang: PanchangEntity)
}
