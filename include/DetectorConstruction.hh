//
// DetectorConstruction.hh
//

// -----------------------------------------------------------------------------
// 头文件保护（Header Guard）
// 用于防止该头文件在同一次编译过程中被重复包含。
// 如果没有这一机制，多次包含会导致类重复定义错误。
//
// #ifndef 会检查 DetectorConstruction_h 是否已经被定义。
// 如果尚未定义，则执行下面的 #define。
// 这里的 “1” 只是一个标记值（通常表示 true），
// 实际上只要被定义即可，数值本身没有特殊含义。
// -----------------------------------------------------------------------------
#ifndef DetectorConstruction_h
#define DetectorConstruction_h 1

#include "G4VUserDetectorConstruction.hh"   // 【GEANT4 内核】用户定义的几何构造基类
#include "globals.hh"                       // 【GEANT4 内核】全局定义

class G4VPhysicalVolume;
class G4LogicalVolume;

// 用户自定义几何构造类，继承自 Geant4 的抽象基类
class DetectorConstruction : public G4VUserDetectorConstruction
{
  public:
    DetectorConstruction();                 // 构造函数,名字必须与类名相同，无返回值
    virtual ~DetectorConstruction();        // 虚析构函数，确保正确释放资源

    virtual G4VPhysicalVolume* Construct(); // 重写基类纯虚函数，用于构建并返回 world 物理体积

  private:
    G4LogicalVolume* fWaterLogical;         // 成员变量，指向水体的逻辑体积，用于后续步骤中识别水体，只能在类内部访问
};

#endif
