//
// SteppingAction.cc
//

#include "SteppingAction.hh"
#include "EventAction.hh"
#include "Config.hh"

#include "G4Step.hh"
#include "G4Event.hh"
#include "G4RunManager.hh"
#include "G4LogicalVolume.hh"
#include "G4OpticalPhoton.hh"
#include "G4Track.hh"
#include "G4VProcess.hh"

SteppingAction::SteppingAction(EventAction* eventAction)
: G4UserSteppingAction(),
  fEventAction(eventAction)
{}

SteppingAction::~SteppingAction()
{}

void SteppingAction::UserSteppingAction(const G4Step* step)
{
  G4Track* track = step->GetTrack();
  G4StepPoint* preStepPoint = step->GetPreStepPoint();
  G4StepPoint* postStepPoint = step->GetPostStepPoint();
  Config* config = Config::GetInstance();
  G4String phantomName = config->GetPhantomVolumeName();
  G4VPhysicalVolume* preVolume = preStepPoint->GetPhysicalVolume();

  // 1) Dose branch first (pre-step in phantom, edep > 0)
  if (config->GetEnableDoseOutput()) {
    if (preVolume && preVolume->GetName() == phantomName && step->GetTotalEnergyDeposit() > 0) {
      G4ThreeVector pos = (preStepPoint->GetPosition() + postStepPoint->GetPosition()) * 0.5;
      G4double energy = step->GetTotalEnergyDeposit();
      G4int pdg = track->GetDefinition()->GetPDGEncoding();
      fEventAction->RecordDoseData(pos.x(), pos.y(), pos.z(), energy, pdg);
    }
  }

  // 2) Cherenkov optical photon branch (only optical photons)
  if (track->GetDefinition() != G4OpticalPhoton::OpticalPhotonDefinition()) {
    return;
  }
  if (!config->GetEnableCherenkovOutput()) return;

  if (track->GetCurrentStepNumber() == 1) {
    const G4VProcess* creatorProcess = track->GetCreatorProcess();
    if (creatorProcess && creatorProcess->GetProcessName() == "Cerenkov") {
      G4ThreeVector position = preStepPoint->GetPosition();
      G4ThreeVector direction = preStepPoint->GetMomentumDirection();
      fEventAction->RecordPhotonCreation(
        track->GetTrackID(),
        position.x(), position.y(), position.z(),
        direction.x(), direction.y(), direction.z()
      );
    }
  }

  G4VPhysicalVolume* postVolume = postStepPoint->GetPhysicalVolume();
  G4String preVolName = (preVolume) ? preVolume->GetName() : "None";
  G4String postVolName = (postVolume) ? postVolume->GetName() : "None";
  bool isKilled = (track->GetTrackStatus() != fAlive);
  bool leavesPhantom = (preVolName == phantomName && postVolName != phantomName);

  if (leavesPhantom) {
    G4ThreeVector position = postStepPoint->GetPosition();
    G4ThreeVector direction = postStepPoint->GetMomentumDirection();
    G4double energy = postStepPoint->GetTotalEnergy();
    fEventAction->RecordPhotonEnd(
      track->GetTrackID(),
      position.x(), position.y(), position.z(),
      direction.x(), direction.y(), direction.z(),
      energy
    );
    track->SetTrackStatus(fStopAndKill);
  } else if (isKilled) {
    if (preVolName == phantomName) {
      G4ThreeVector position = postStepPoint->GetPosition();
      G4ThreeVector direction = postStepPoint->GetMomentumDirection();
      G4double energy = postStepPoint->GetTotalEnergy();
      fEventAction->RecordPhotonEnd(
        track->GetTrackID(),
        position.x(), position.y(), position.z(),
        direction.x(), direction.y(), direction.z(),
        energy
      );
    }
  }
}
